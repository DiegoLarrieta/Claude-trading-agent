#!/usr/bin/env python
"""Mechanical strategy backtester — deterministic, rule-shaped parts ONLY.

Replays a trigger rule (big daily move + volume surge, like the scanner's)
over yfinance daily history and simulates a fixed exit discipline
(stop / target / time), producing the statistics that tune
config/scanner.yaml with evidence instead of guesses.

NEVER used to backtest LLM judgment (lookahead bias — the model knows how
history ended). No LLM in this file.

Usage:
  backtest.py --years 2 --direction drop --move 5 --vol 2.5 \
              --stop 5 --target 8 --hold 10 [--tickers AAPL,MSFT,...]
"""
import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Default universe: liquid, $2B+ names across sectors (mirrors scanner rules).
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "AVGO", "CRM",
    "ORCL", "ADBE", "NFLX", "INTC", "MU", "QCOM", "SMCI", "PLTR", "UBER", "SHOP",
    "JPM", "BAC", "GS", "MS", "SCHW", "V", "MA", "PYPL", "COIN", "AXP",
    "UNH", "JNJ", "PFE", "MRK", "LLY", "ABBV", "TMO", "AMGN", "GILD", "MRNA",
    "XOM", "CVX", "COP", "OXY", "SLB", "DVN", "FCX", "NEM", "GE", "CAT",
    "WMT", "COST", "TGT", "HD", "LOW", "NKE", "SBUX", "MCD", "DIS", "BA",
]


@dataclass
class Trade:
    ticker: str
    entry_date: str
    entry: float
    exit_date: str
    exit: float
    exit_reason: str  # stop | target | time
    pnl_pct: float


# ── pure logic (unit-tested) ────────────────────────────────────────


def find_triggers(closes: list[float], volumes: list[float],
                  move_pct: float, vol_mult: float, direction: str,
                  avg_window: int = 20) -> list[int]:
    """Indices i where day i moved >= move_pct vs i-1 in `direction`
    AND volume[i] >= vol_mult * avg(volume[i-window:i])."""
    out = []
    for i in range(avg_window, len(closes)):
        prev, cur = closes[i - 1], closes[i]
        if not prev:
            continue
        chg = (cur - prev) / prev * 100
        hit = chg <= -move_pct if direction == "drop" else chg >= move_pct
        if not hit:
            continue
        avg_vol = sum(volumes[i - avg_window:i]) / avg_window
        if avg_vol and volumes[i] >= vol_mult * avg_vol:
            out.append(i)
    return out


def simulate_trade(closes: list[float], entry_i: int,
                   stop_pct: float, target_pct: float, max_hold: int) -> tuple[int, str, float]:
    """Buy at close of trigger day; exit on stop/target/time using daily
    closes (conservative: no intraday peeking). Returns (exit_i, reason, pnl_pct)."""
    entry = closes[entry_i]
    stop = entry * (1 - stop_pct / 100)
    target = entry * (1 + target_pct / 100)
    last = min(entry_i + max_hold, len(closes) - 1)
    for i in range(entry_i + 1, last + 1):
        c = closes[i]
        if c <= stop:
            return i, "stop", round((stop - entry) / entry * 100, 2)
        if c >= target:
            return i, "target", round((target - entry) / entry * 100, 2)
    return last, "time", round((closes[last] - entry) / entry * 100, 2)


def aggregate(trades: list[Trade]) -> dict:
    if not trades:
        return {"trades": 0}
    wins = [t for t in trades if t.pnl_pct > 0]
    pnls = [t.pnl_pct for t in trades]
    by_reason = {}
    for t in trades:
        by_reason[t.exit_reason] = by_reason.get(t.exit_reason, 0) + 1
    return {
        "trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1),
        "avg_pnl_pct": round(sum(pnls) / len(pnls), 2),
        "expectancy_usd_per_200": round(sum(pnls) / len(pnls) * 2, 2),
        "best_pct": max(pnls), "worst_pct": min(pnls),
        "exits": by_reason,
    }


# ── I/O shell ───────────────────────────────────────────────────────


def run(tickers, years, direction, move, vol, stop, target, hold) -> dict:
    import yfinance as yf
    trades: list[Trade] = []
    skipped = []
    data = yf.download(tickers, period=f"{years}y", interval="1d",
                       group_by="ticker", auto_adjust=True, progress=False, threads=True)
    for t in tickers:
        try:
            df = data[t].dropna()
            closes, vols = df["Close"].tolist(), df["Volume"].tolist()
            dates = [d.strftime("%Y-%m-%d") for d in df.index]
        except Exception:
            skipped.append(t)
            continue
        last_exit = -1
        for i in find_triggers(closes, vols, move, vol, direction):
            if i <= last_exit:  # one position per ticker at a time
                continue
            if i >= len(closes) - 1:
                continue
            exit_i, reason, pnl = simulate_trade(closes, i, stop, target, hold)
            last_exit = exit_i
            trades.append(Trade(t, dates[i], round(closes[i], 2),
                                dates[exit_i], round(closes[exit_i], 2), reason, pnl))
    stats = aggregate(trades)
    stats["params"] = {"direction": direction, "move_pct": move, "vol_mult": vol,
                       "stop_pct": stop, "target_pct": target, "max_hold_days": hold,
                       "years": years, "universe_size": len(tickers), "skipped": skipped}
    stats["sample_trades"] = [asdict(t) for t in trades[-10:]]
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=2)
    ap.add_argument("--direction", choices=["drop", "pop"], default="drop")
    ap.add_argument("--move", type=float, default=5.0, help="trigger |%% move| vs prior close")
    ap.add_argument("--vol", type=float, default=2.5, help="volume multiple vs 20d avg")
    ap.add_argument("--stop", type=float, default=5.0)
    ap.add_argument("--target", type=float, default=8.0)
    ap.add_argument("--hold", type=int, default=10, help="max holding days")
    ap.add_argument("--tickers", type=str, default="")
    a = ap.parse_args()
    tickers = [t.strip().upper() for t in a.tickers.split(",") if t.strip()] or DEFAULT_UNIVERSE
    print(json.dumps(run(tickers, a.years, a.direction, a.move, a.vol,
                         a.stop, a.target, a.hold), indent=2))
