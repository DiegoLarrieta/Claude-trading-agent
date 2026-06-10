"""Unit tests for the backtester's pure logic — no network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from backtest import find_triggers, simulate_trade, aggregate, Trade


def flat(n, price=100.0, vol=1000.0):
    return [price] * n, [vol] * n


# ── find_triggers ───────────────────────────────────────────────────

def test_no_triggers_on_flat_series():
    closes, vols = flat(40)
    assert find_triggers(closes, vols, 5, 2.5, "drop") == []


def test_drop_trigger_needs_both_move_and_volume():
    closes, vols = flat(40)
    closes[30] = 94.0  # -6% day
    assert find_triggers(closes, vols, 5, 2.5, "drop") == []  # volume normal
    vols[30] = 3000.0  # 3x avg volume
    assert find_triggers(closes, vols, 5, 2.5, "drop") == [30]


def test_direction_pop_vs_drop():
    closes, vols = flat(40)
    closes[30], vols[30] = 106.0, 3000.0  # +6% on 3x vol
    assert find_triggers(closes, vols, 5, 2.5, "drop") == []
    assert find_triggers(closes, vols, 5, 2.5, "pop") == [30]


def test_no_trigger_inside_warmup_window():
    closes, vols = flat(40)
    closes[10], vols[10] = 90.0, 9000.0
    assert find_triggers(closes, vols, 5, 2.5, "drop") == []


# ── simulate_trade ──────────────────────────────────────────────────

def test_stop_exit():
    closes = [100, 100, 94, 90]  # entry at i=1, stop 5% => 95
    exit_i, reason, pnl = simulate_trade(closes, 1, 5, 8, 10)
    assert (exit_i, reason, pnl) == (2, "stop", -5.0)


def test_target_exit():
    closes = [100, 100, 109, 120]
    exit_i, reason, pnl = simulate_trade(closes, 1, 5, 8, 10)
    assert (exit_i, reason, pnl) == (2, "target", 8.0)


def test_time_exit_at_max_hold():
    closes = [100.0] * 20
    closes[6] = 101.0
    exit_i, reason, pnl = simulate_trade(closes, 1, 5, 8, 5)
    assert (exit_i, reason) == (6, "time")
    assert pnl == 1.0


def test_time_exit_clamped_to_series_end():
    closes = [100, 100, 101]
    exit_i, reason, _ = simulate_trade(closes, 1, 5, 8, 10)
    assert (exit_i, reason) == (2, "time")


def test_stop_checked_before_target_same_day_conservative():
    # a day that closes below stop exits as stop even if a later day would hit target
    closes = [100, 100, 94, 130]
    _, reason, _ = simulate_trade(closes, 1, 5, 8, 10)
    assert reason == "stop"


# ── aggregate ───────────────────────────────────────────────────────

def T(pnl, reason="target"):
    return Trade("X", "d", 100, "d", 100 + pnl, reason, pnl)


def test_aggregate_empty():
    assert aggregate([]) == {"trades": 0}


def test_aggregate_stats():
    s = aggregate([T(8.0), T(-5.0, "stop"), T(8.0), T(1.0, "time")])
    assert s["trades"] == 4
    assert s["win_rate_pct"] == 75.0
    assert s["avg_pnl_pct"] == 3.0
    assert s["expectancy_usd_per_200"] == 6.0
    assert s["exits"] == {"target": 2, "stop": 1, "time": 1}
