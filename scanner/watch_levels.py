#!/usr/bin/env python
"""Watch-level alerting — committee-set price tripwires. No LLM here.

The committee parks conditional levels in config/watch-levels.yaml
("re-review NVDA if it touches 196"). During market hours the watcher
checks them alongside position stops and alerts Diego (macOS + Telegram)
when one prints. An alert means "convene the review", never "buy".

Each level fires at most once per day; fired state lives in
journal/.watch-alerts.json.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEVELS_FILE = ROOT / "config" / "watch-levels.yaml"
STATE_FILE = ROOT / "journal" / ".watch-alerts.json"


# ── pure logic (unit-tested, no I/O) ────────────────────────────────


def level_id(level: dict) -> str:
    return f"{level['ticker']}:{level['when']}:{level['level']}"


def is_triggered(level: dict, price: float) -> bool:
    if level["when"] == "at_or_below":
        return price <= level["level"]
    if level["when"] == "at_or_above":
        return price >= level["level"]
    return False  # unknown comparator: never guess


def check_levels(levels: list[dict], prices: dict[str, float],
                 fired_today: set[str]) -> list[dict]:
    """Return levels that just triggered and haven't fired today.

    Missing prices are skipped — no data is never a trigger.
    """
    hits = []
    for lv in levels:
        price = prices.get(lv["ticker"])
        if price is None or level_id(lv) in fired_today:
            continue
        if is_triggered(lv, price):
            hits.append({**lv, "price": price})
    return hits


# ── I/O shell ───────────────────────────────────────────────────────


def load_levels() -> list[dict]:
    import yaml
    if not LEVELS_FILE.exists():
        return []
    data = yaml.safe_load(LEVELS_FILE.read_text()) or {}
    return data.get("levels") or []


def load_fired_today(today: str) -> set[str]:
    if not STATE_FILE.exists():
        return set()
    try:
        state = json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        return set()
    return set(state.get(today, []))


def record_fired(today: str, ids: list[str]) -> None:
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            state = {}
    state = {today: sorted(set(state.get(today, [])) | set(ids))}  # keep only today
    STATE_FILE.write_text(json.dumps(state, indent=2))


def check_once(notify_fn=None) -> list[dict]:
    """Fetch prices for watched tickers, alert on fresh triggers."""
    levels = load_levels()
    if not levels:
        return []
    if notify_fn is None:
        from monitor import notify as notify_fn
    import yfinance as yf

    prices = {}
    for t in {lv["ticker"] for lv in levels}:
        try:
            prices[t] = yf.Ticker(t).fast_info.last_price
        except Exception as e:
            print(f"WARN watch-level price fetch failed for {t}: {e}", file=sys.stderr)

    today = datetime.now(timezone.utc).date().isoformat()
    hits = check_levels(levels, prices, load_fired_today(today))
    for h in hits:
        msg = f"WATCH LEVEL HIT: {h['ticker']} ${h['price']:.2f} ({h['when']} {h['level']}) — {h['note']}"
        print(msg)
        notify_fn("Trade Agent — watch level", msg)
    if hits:
        record_fired(today, [level_id(h) for h in hits])
    return hits


if __name__ == "__main__":
    check_once()
