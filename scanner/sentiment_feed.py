#!/usr/bin/env python
"""Stocktwits sentiment feed — deterministic crowd-data fetcher.

Pulls the public symbol stream for a ticker and produces a neutral,
numeric summary for the sentiment analyst. This file measures the crowd;
it never interprets it — interpretation is the analyst's job. No LLM here.

Usage: sentiment_feed.py TICKER [TICKER...]   → JSON summary to stdout
"""
import json
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone

API = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
UA = "trade-agent-research/1.0 (personal portfolio research)"


# ── pure logic (unit-tested) ────────────────────────────────────────


def summarize_messages(messages: list[dict]) -> dict:
    """Reduce raw Stocktwits messages to neutral crowd metrics.

    Counts self-tagged sentiment (users label their own posts
    Bullish/Bearish), measures chatter volume and recency, and samples
    the most-followed authors' posts as representative quotes.
    """
    tags = Counter()
    timestamps = []
    for m in messages:
        sent = (m.get("entities") or {}).get("sentiment") or {}
        tags[sent.get("basic") or "Untagged"] += 1
        if m.get("created_at"):
            timestamps.append(m["created_at"])

    tagged = tags["Bullish"] + tags["Bearish"]
    bullish_ratio = round(tags["Bullish"] / tagged, 2) if tagged else None

    by_followers = sorted(
        messages,
        key=lambda m: (m.get("user") or {}).get("followers", 0),
        reverse=True,
    )
    samples = [
        {
            "body": (m.get("body") or "")[:200],
            "sentiment_tag": ((m.get("entities") or {}).get("sentiment") or {}).get("basic"),
            "author_followers": (m.get("user") or {}).get("followers", 0),
        }
        for m in by_followers[:5]
    ]

    return {
        "message_count": len(messages),
        "bullish": tags["Bullish"],
        "bearish": tags["Bearish"],
        "untagged": tags["Untagged"],
        "bullish_ratio_of_tagged": bullish_ratio,
        "newest": max(timestamps) if timestamps else None,
        "oldest": min(timestamps) if timestamps else None,
        "top_author_samples": samples,
    }


# ── I/O shell ───────────────────────────────────────────────────────


def fetch_stream(ticker: str) -> dict:
    req = urllib.request.Request(API.format(ticker=ticker.upper()), headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        summary = summarize_messages(data.get("messages", []))
        summary["ticker"] = ticker.upper()
        summary["watchers"] = (data.get("symbol") or {}).get("watchlist_count")
        summary["source"] = "stocktwits"
        summary["fetched_at"] = datetime.now(timezone.utc).isoformat()
        return summary
    except Exception as e:
        return {"ticker": ticker.upper(), "source": "stocktwits",
                "error": f"DATA UNAVAILABLE: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: sentiment_feed.py TICKER [TICKER...]", file=sys.stderr)
        sys.exit(2)
    print(json.dumps([fetch_stream(t) for t in sys.argv[1:]], indent=2))
