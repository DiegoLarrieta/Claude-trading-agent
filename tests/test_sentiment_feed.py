"""Unit tests for the Stocktwits summary logic — no network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from sentiment_feed import summarize_messages


def msg(body="x", sentiment=None, followers=0, created="2026-06-10T18:00:00Z"):
    return {
        "body": body,
        "created_at": created,
        "user": {"followers": followers},
        "entities": {"sentiment": {"basic": sentiment} if sentiment else None},
    }


def test_empty_stream():
    s = summarize_messages([])
    assert s["message_count"] == 0
    assert s["bullish_ratio_of_tagged"] is None
    assert s["top_author_samples"] == []


def test_tag_counting_and_ratio():
    msgs = [msg(sentiment="Bullish")] * 3 + [msg(sentiment="Bearish")] + [msg()] * 2
    s = summarize_messages(msgs)
    assert (s["bullish"], s["bearish"], s["untagged"]) == (3, 1, 2)
    assert s["bullish_ratio_of_tagged"] == 0.75


def test_all_untagged_gives_no_ratio():
    s = summarize_messages([msg(), msg()])
    assert s["bullish_ratio_of_tagged"] is None


def test_samples_ranked_by_followers_capped_at_5():
    msgs = [msg(body=f"m{i}", followers=i) for i in range(8)]
    s = summarize_messages(msgs)
    assert len(s["top_author_samples"]) == 5
    assert s["top_author_samples"][0]["author_followers"] == 7


def test_sample_body_truncated():
    s = summarize_messages([msg(body="a" * 500)])
    assert len(s["top_author_samples"][0]["body"]) == 200


def test_malformed_messages_dont_crash():
    s = summarize_messages([{"body": None, "user": None, "entities": None}])
    assert s["message_count"] == 1
    assert s["untagged"] == 1
