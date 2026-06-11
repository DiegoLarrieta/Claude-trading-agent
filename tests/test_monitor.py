"""Unit tests for the stop monitor's pure logic — no network, no files."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from datetime import datetime
from zoneinfo import ZoneInfo

from monitor import find_breaches, execute_stop_exit, market_is_open


def make_position(ticker="SMCI", shares=5, fill=33.48, stop=31.50):
    return {
        "ticker": ticker, "side": "buy", "shares": shares,
        "fill_price": fill, "stop": stop,
        "opened_at": "2026-06-10T16:50:00+00:00",
        "thesis": "t", "owner": "diego-discretionary", "simulated": True,
    }


def make_portfolio(positions, cash=1192.18):
    return {"cash_usd": cash, "positions": positions, "closed_trades": [], "simulated": True}


# ── find_breaches ───────────────────────────────────────────────────

def test_no_breach_above_stop():
    assert find_breaches([make_position()], {"SMCI": 32.00}) == []


def test_breach_at_stop_exactly():
    pos = make_position()
    assert find_breaches([pos], {"SMCI": 31.50}) == [pos]


def test_breach_below_stop():
    pos = make_position()
    assert find_breaches([pos], {"SMCI": 30.00}) == [pos]


def test_missing_price_is_not_a_breach():
    assert find_breaches([make_position()], {}) == []


def test_multiple_positions_only_breached_returned():
    a = make_position("SMCI", stop=31.50)
    b = make_position("DNTH", shares=2, fill=70.20, stop=64.00)
    breaches = find_breaches([a, b], {"SMCI": 31.00, "DNTH": 75.00})
    assert breaches == [a]


# ── execute_stop_exit ───────────────────────────────────────────────

def test_exit_math_and_cash_credit():
    pos = make_position()  # 5 sh @ 33.48, stop 31.50
    pf = make_portfolio([pos], cash=100.0)
    closed = execute_stop_exit(pf, pos, "2026-06-10T18:00:00+00:00")
    assert closed["exit_price"] == 31.50
    assert closed["pnl_usd"] == round(5 * 31.50 - 5 * 33.48, 2)  # -9.90
    assert pf["cash_usd"] == round(100.0 + 5 * 31.50, 2)
    assert pf["positions"] == []
    assert pf["closed_trades"] == [closed]


def test_exit_fills_at_stop_when_price_at_or_above_stop():
    """Normal breach: live price at the stop level fills at the stop."""
    pos = make_position(stop=31.50)
    pf = make_portfolio([pos])
    closed = execute_stop_exit(pf, pos, "now", live_price=31.50)
    assert closed["exit_price"] == 31.50
    assert closed["exit_reason"] == "stop"


def test_gap_below_stop_fills_at_live_price():
    """Honest fill: a gap below the stop fills at the gapped price, not the stop."""
    pos = make_position(stop=31.50)  # 5 sh @ 33.48
    pf = make_portfolio([pos], cash=0.0)
    closed = execute_stop_exit(pf, pos, "now", live_price=29.245)
    assert closed["exit_price"] == 29.245
    assert closed["exit_reason"] == "stop_gap"
    assert pf["cash_usd"] == round(5 * 29.245, 2)
    # pnl is computed from cent-rounded proceeds and cost, so compare the same way
    assert closed["pnl_usd"] == round(round(5 * 29.245, 2) - round(5 * 33.48, 2), 2)


def test_no_live_price_falls_back_to_stop():
    pos = make_position(stop=31.50)
    pf = make_portfolio([pos])
    closed = execute_stop_exit(pf, pos, "now")
    assert closed["exit_price"] == 31.50
    assert closed["exit_reason"] == "stop"


def test_exit_only_removes_matching_position():
    a = make_position("SMCI")
    b = make_position("DNTH", shares=2, fill=70.20, stop=64.00)
    pf = make_portfolio([a, b])
    execute_stop_exit(pf, a, "now")
    assert [p["ticker"] for p in pf["positions"]] == ["DNTH"]


def test_fractional_shares_exit_math():
    pos = make_position("CASY", shares=0.2296, fill=871.15, stop=830.00)
    pf = make_portfolio([pos], cash=0.0)
    closed = execute_stop_exit(pf, pos, "now")
    assert pf["cash_usd"] == round(0.2296 * 830.00, 2)
    assert closed["pnl_usd"] == round(0.2296 * 830.00 - 0.2296 * 871.15, 2)


# ── market_is_open ──────────────────────────────────────────────────

ET = ZoneInfo("America/New_York")


def test_market_open_midday():
    assert market_is_open(datetime(2026, 6, 10, 13, 0, tzinfo=ET))


def test_market_closed_premarket_and_after():
    assert not market_is_open(datetime(2026, 6, 10, 9, 29, tzinfo=ET))
    assert not market_is_open(datetime(2026, 6, 10, 16, 0, tzinfo=ET))


def test_market_closed_weekend():
    assert not market_is_open(datetime(2026, 6, 13, 13, 0, tzinfo=ET))  # Saturday
