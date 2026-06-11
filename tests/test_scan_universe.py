"""Unit tests for the scanner's universe/earnings pure logic — no network."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from scan import days_to_earnings, theme_of, triggers_for

UNIVERSE = {
    "watchlist_triggers": {"pct_move_intraday": 2.5, "volume_multiple": 2.0},
    "themes": {
        "ai-chips": ["NVDA", "AMD"],
        "ai-energy": ["VST"],
    },
}
BASE = {"pct_move_intraday": 4.0, "volume_multiple": 3.0, "week52_extreme": True}


# ── theme_of ────────────────────────────────────────────────────────

def test_watchlist_ticker_has_theme():
    assert theme_of("NVDA", UNIVERSE) == "ai-chips"
    assert theme_of("VST", UNIVERSE) == "ai-energy"


def test_stranger_has_no_theme():
    assert theme_of("CASY", UNIVERSE) is None


def test_empty_universe_is_safe():
    assert theme_of("NVDA", {}) is None


# ── triggers_for ────────────────────────────────────────────────────

def test_watchlist_gets_sensitive_triggers():
    trig = triggers_for("NVDA", UNIVERSE, BASE)
    assert trig["pct_move_intraday"] == 2.5
    assert trig["volume_multiple"] == 2.0
    assert trig["week52_extreme"] is True  # non-overridden keys survive


def test_stranger_keeps_base_triggers():
    assert triggers_for("CASY", UNIVERSE, BASE) == BASE


def test_watchlist_without_overrides_keeps_base():
    uni = {"themes": {"ai-chips": ["NVDA"]}}
    assert triggers_for("NVDA", uni, BASE) == BASE


# ── days_to_earnings ────────────────────────────────────────────────

TODAY = date(2026, 6, 11)


def test_next_earnings_in_13_days():
    dates = [date(2026, 6, 24), date(2026, 9, 22)]
    assert days_to_earnings(dates, TODAY) == 13


def test_earnings_today_is_zero():
    assert days_to_earnings([date(2026, 6, 11)], TODAY) == 0


def test_past_dates_ignored():
    assert days_to_earnings([date(2026, 3, 10), date(2026, 6, 30)], TODAY) == 19


def test_no_future_dates_is_none():
    assert days_to_earnings([date(2026, 3, 10)], TODAY) is None
    assert days_to_earnings([], TODAY) is None
