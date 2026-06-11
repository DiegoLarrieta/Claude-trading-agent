"""Unit tests for the proposal validator's pure logic — no network, no files."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from validate_proposal import validate

NOW = datetime(2026, 6, 11, 15, 0, tzinfo=timezone.utc)


def make_limits(**over):
    base = {
        "kill_switch": False,
        "trade_size_usd": 200,
        "allow_fractional_shares": True,
        "max_trades_per_day": 3,
        "max_open_positions": 5,
        "max_total_exposure_usd": 1400,
        "allow_short_selling": False,
        "ticker_blacklist": [],
        "max_price_drift_pct": 1.0,
    }
    base.update(over)
    return base


def make_portfolio(positions=None, closed=None, cash=1349.68):
    return {"cash_usd": cash, "positions": positions or [],
            "closed_trades": closed or [], "simulated": True}


def make_proposal(**over):
    base = {"ticker": "ABCD", "side": "buy", "shares": 2,
            "limit": 95.0, "stop": 89.0, "horizon": "swing"}
    base.update(over)
    return base


def held(ticker="DNTH", shares=2, fill=70.20, opened="2026-06-10T16:12:35+00:00"):
    return {"ticker": ticker, "shares": shares, "fill_price": fill,
            "opened_at": opened, "side": "buy", "stop": fill * 0.9}


# ── the happy path ──────────────────────────────────────────────────

def test_clean_proposal_is_valid():
    assert validate(make_proposal(), make_portfolio(), make_limits(),
                    live_price=95.2, now=NOW) == []


# ── stop geometry: the day-one lesson ───────────────────────────────

def test_stop_above_entry_rejected():
    v = validate(make_proposal(stop=99.0), make_portfolio(), make_limits(), now=NOW)
    assert any("at/above entry" in x for x in v)


def test_stop_equal_entry_rejected():
    v = validate(make_proposal(stop=95.0), make_portfolio(), make_limits(), now=NOW)
    assert any("at/above entry" in x for x in v)


def test_absurdly_deep_stop_rejected():
    v = validate(make_proposal(stop=50.0), make_portfolio(), make_limits(), now=NOW)
    assert any("30% below entry" in x for x in v)


# ── master switches ─────────────────────────────────────────────────

def test_kill_switch_blocks_everything():
    v = validate(make_proposal(), make_portfolio(), make_limits(kill_switch=True), now=NOW)
    assert any("kill_switch" in x for x in v)


def test_short_selling_rejected():
    v = validate(make_proposal(side="sell"), make_portfolio(), make_limits(), now=NOW)
    assert any("short selling" in x for x in v)


def test_blacklisted_ticker_rejected():
    v = validate(make_proposal(ticker="ABCD"), make_portfolio(),
                 make_limits(ticker_blacklist=["ABCD"]), now=NOW)
    assert any("blacklisted" in x for x in v)


# ── sizing and caps ─────────────────────────────────────────────────

def test_oversized_position_rejected():
    v = validate(make_proposal(shares=3), make_portfolio(), make_limits(), now=NOW)
    assert any("trade_size_usd" in x for x in v)


def test_cost_above_cash_rejected():
    v = validate(make_proposal(), make_portfolio(cash=100.0), make_limits(), now=NOW)
    assert any("available cash" in x for x in v)


def test_max_open_positions_enforced():
    positions = [held(t) for t in ("AA", "BB", "CC", "DD", "EE")]
    v = validate(make_proposal(), make_portfolio(positions, cash=10000),
                 make_limits(max_total_exposure_usd=99999), now=NOW)
    assert any("max_open_positions" in x for x in v)


def test_no_adding_to_existing_position():
    v = validate(make_proposal(ticker="DNTH"), make_portfolio([held("DNTH")]),
                 make_limits(), now=NOW)
    assert any("already holding DNTH" in x for x in v)


def test_trades_per_day_counts_opened_and_closed_today():
    today = "2026-06-11T14:00:00+00:00"
    positions = [held("AA", opened=today), held("BB", opened=today)]
    closed = [{"ticker": "CC", "shares": 1, "fill_price": 10, "opened_at": today}]
    v = validate(make_proposal(), make_portfolio(positions, closed, cash=10000),
                 make_limits(max_total_exposure_usd=99999), now=NOW)
    assert any("max_trades_per_day" in x for x in v)


def test_yesterdays_trades_dont_count_today():
    positions = [held("AA"), held("BB")]  # opened 2026-06-10, NOW is 06-11
    v = validate(make_proposal(), make_portfolio(positions),
                 make_limits(), live_price=95.2, now=NOW)
    assert v == []


def test_exposure_cap_enforced():
    positions = [held("AA", shares=10, fill=130.0)]  # $1300 of $1400 cap used
    v = validate(make_proposal(), make_portfolio(positions), make_limits(), now=NOW)
    assert any("max_total_exposure_usd" in x for x in v)


# ── freshness ───────────────────────────────────────────────────────

def test_stale_limit_price_rejected():
    v = validate(make_proposal(limit=95.0, stop=89.0), make_portfolio(),
                 make_limits(), live_price=100.0, now=NOW)
    assert any("from live price" in x for x in v)


def test_no_live_price_skips_drift_check():
    assert validate(make_proposal(), make_portfolio(), make_limits(),
                    live_price=None, now=NOW) == []


# ── misc ────────────────────────────────────────────────────────────

def test_bad_horizon_rejected():
    v = validate(make_proposal(horizon="forever"), make_portfolio(),
                 make_limits(), now=NOW)
    assert any("horizon" in x for x in v)


def test_fractional_shares_blocked_when_disallowed():
    v = validate(make_proposal(shares=0.5), make_portfolio(),
                 make_limits(allow_fractional_shares=False), now=NOW)
    assert any("fractional" in x for x in v)


def test_all_violations_reported_not_just_first():
    v = validate(make_proposal(stop=99.0, shares=50), make_portfolio(cash=100),
                 make_limits(kill_switch=True), now=NOW)
    assert len(v) >= 3
