"""Unit tests for mechanical exit rules (adjust_stops) — no network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from monitor import adjust_stops

RULES = {"breakeven_trigger_pct": 8.0, "trail_trigger_pct": 12.0, "trail_distance_pct": 6.0}


def pos(ticker="DNTH", fill=70.20, stop=64.00, shares=2, high_water=None):
    p = {"ticker": ticker, "side": "buy", "shares": shares,
         "fill_price": fill, "stop": stop, "opened_at": "t"}
    if high_water is not None:
        p["high_water"] = high_water
    return p


def test_small_gain_no_change():
    p = pos()  # +5% < 8% trigger
    assert adjust_stops([p], {"DNTH": 73.71}, RULES) == []
    assert p["stop"] == 64.00


def test_breakeven_move_at_8pct():
    p = pos()  # +8.4%
    changed = adjust_stops([p], {"DNTH": 76.10}, RULES)
    assert changed == [p]
    assert p["stop"] == 70.20  # = entry: trade can no longer lose
    assert p["prior_stop"] == 64.00


def test_trailing_at_12pct_beats_breakeven():
    p = pos()  # +14%: trail = 80.03 * 0.94 = 75.23 > entry 70.20
    adjust_stops([p], {"DNTH": 80.03}, RULES)
    assert p["stop"] == round(80.03 * 0.94, 2)


def test_high_water_persists_trail_never_drops():
    p = pos(high_water=85.00, stop=79.90)  # trail already set from high 85
    # price falls back to 80 — high_water stays 85, stop must NOT drop
    changed = adjust_stops([p], {"DNTH": 80.00}, RULES)
    assert changed == []
    assert p["stop"] == 79.90
    assert p["high_water"] == 85.00


def test_stop_never_lowered_even_if_rules_would():
    p = pos(stop=75.00)  # manually-tightened stop above what rules compute
    adjust_stops([p], {"DNTH": 76.10}, RULES)  # breakeven would be 70.20
    assert p["stop"] == 75.00


def test_missing_price_no_change():
    p = pos()
    assert adjust_stops([p], {}, RULES) == []
    assert "high_water" not in p


def test_loss_position_untouched():
    p = pos(fill=33.48, stop=31.50, ticker="SMCI")
    adjust_stops([p], {"SMCI": 32.00}, RULES)
    assert p["stop"] == 31.50


def test_fractional_shares_work():
    p = pos(ticker="CASY", fill=871.15, stop=830.00, shares=0.2296)
    adjust_stops([p], {"CASY": 941.00}, RULES)  # +8.02% -> breakeven
    assert p["stop"] == 871.15
