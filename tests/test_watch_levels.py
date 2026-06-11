"""Unit tests for watch-level tripwire logic — no network, no files."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from watch_levels import check_levels, is_triggered, level_id

NVDA = {"ticker": "NVDA", "when": "at_or_below", "level": 196.0, "note": "core zone"}
UNIT = {"ticker": "UNIT", "when": "at_or_above", "level": 12.45, "note": "breakout"}


def test_at_or_below_triggers():
    assert is_triggered(NVDA, 195.99)
    assert is_triggered(NVDA, 196.0)
    assert not is_triggered(NVDA, 196.01)


def test_at_or_above_triggers():
    assert is_triggered(UNIT, 12.45)
    assert is_triggered(UNIT, 13.0)
    assert not is_triggered(UNIT, 12.44)


def test_unknown_comparator_never_triggers():
    assert not is_triggered({"ticker": "X", "when": "sideways", "level": 1}, 1)


def test_check_levels_returns_fresh_hits_with_price():
    hits = check_levels([NVDA, UNIT], {"NVDA": 195.0, "UNIT": 12.0}, set())
    assert len(hits) == 1
    assert hits[0]["ticker"] == "NVDA" and hits[0]["price"] == 195.0


def test_already_fired_today_is_suppressed():
    fired = {level_id(NVDA)}
    assert check_levels([NVDA], {"NVDA": 190.0}, fired) == []


def test_missing_price_is_not_a_trigger():
    assert check_levels([NVDA], {}, set()) == []


def test_multiple_hits_all_reported():
    hits = check_levels([NVDA, UNIT], {"NVDA": 195.0, "UNIT": 12.5}, set())
    assert {h["ticker"] for h in hits} == {"NVDA", "UNIT"}
