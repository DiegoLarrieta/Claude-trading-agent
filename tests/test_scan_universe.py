"""Unit tests for the scanner's universe/earnings pure logic — no network."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from scan import budget_alerts, days_to_earnings, pre_triage_kill, theme_of, triggers_for

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


# ── pre_triage_kill ─────────────────────────────────────────────────

PT_CFG = {"earnings_window_days": 1, "extraordinary_pct_multiple": 2.0}


def test_earnings_reaction_killed_mechanically():
    # +5% the day after earnings: explained move, under the 8% extraordinary bar
    assert pre_triage_kill(5.0, 0, False, 4.0, PT_CFG) is not None
    assert pre_triage_kill(-6.0, 1, False, 4.0, PT_CFG) is not None


def test_extraordinary_earnings_reaction_survives():
    assert pre_triage_kill(9.0, 0, False, 4.0, PT_CFG) is None
    assert pre_triage_kill(-8.0, 0, False, 4.0, PT_CFG) is None  # exactly at the bar


def test_watchlist_and_non_earnings_moves_survive():
    assert pre_triage_kill(5.0, 0, True, 4.0, PT_CFG) is None  # watchlist exempt
    assert pre_triage_kill(5.0, 5, False, 4.0, PT_CFG) is None  # earnings far away
    assert pre_triage_kill(5.0, None, False, 4.0, PT_CFG) is None  # unknown calendar


def test_missing_config_disables_pre_triage():
    assert pre_triage_kill(5.0, 0, False, 4.0, {}) is None


# ── budget_alerts ───────────────────────────────────────────────────

def test_budget_thresholds_fire_once_each():
    assert budget_alerts(47, 60, []) == []          # 78% — quiet
    assert budget_alerts(48, 60, []) == [80]        # 80% — warn
    assert budget_alerts(48, 60, [80]) == []        # already announced
    assert budget_alerts(60, 60, [80]) == [100]     # exhausted
    assert budget_alerts(60, 60, [80, 100]) == []   # never repeats


def test_budget_jump_crosses_both_at_once():
    assert budget_alerts(60, 60, []) == [80, 100]
