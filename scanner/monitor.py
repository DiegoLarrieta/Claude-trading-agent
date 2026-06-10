#!/usr/bin/env python
"""Position stop monitor — deterministic safety layer.

Checks open positions against their stops; on breach, executes a
simulated exit at the stop price (conservative: assumes the stop filled
at its level, not better) and notifies via macOS notification.

Usage:
  monitor.py once          # single check (cron/manual)
  monitor.py loop          # continuous during market hours
No LLM anywhere in this file.
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO = ROOT / "journal" / "portfolio.json"
HEARTBEAT = ROOT / "journal" / ".monitor-heartbeat"
ET = ZoneInfo("America/New_York")


# ── pure logic (unit-tested, no I/O) ────────────────────────────────


def find_breaches(positions: list[dict], prices: dict[str, float]) -> list[dict]:
    """Return positions whose stop is breached at current prices.

    Long positions breach when price <= stop. Unknown prices are skipped
    (no data is never treated as a breach).
    """
    breaches = []
    for pos in positions:
        price = prices.get(pos["ticker"])
        if price is None:
            continue
        if pos["side"] == "buy" and price <= pos["stop"]:
            breaches.append(pos)
    return breaches


def execute_stop_exit(portfolio: dict, position: dict, now_iso: str) -> dict:
    """Close a position at its stop price. Returns the closed-trade record.

    Conservative fill assumption: exit AT the stop, even if the live
    price is lower — real stops rarely fill better than their level.
    """
    exit_price = position["stop"]
    proceeds = round(position["shares"] * exit_price, 2)
    cost = round(position["shares"] * position["fill_price"], 2)
    closed = {
        **position,
        "closed_at": now_iso,
        "exit_price": exit_price,
        "exit_reason": "stop",
        "pnl_usd": round(proceeds - cost, 2),
        "pnl_pct": round((proceeds - cost) / cost * 100, 2),
    }
    portfolio["positions"] = [
        p for p in portfolio["positions"]
        if not (p["ticker"] == position["ticker"] and p["opened_at"] == position["opened_at"])
    ]
    portfolio["closed_trades"].append(closed)
    portfolio["cash_usd"] = round(portfolio["cash_usd"] + proceeds, 2)
    return closed


def market_is_open(now_et: datetime) -> bool:
    if now_et.weekday() >= 5:
        return False
    minutes = now_et.hour * 60 + now_et.minute
    return (9 * 60 + 30) <= minutes < (16 * 60)


# ── I/O shell ───────────────────────────────────────────────────────


def fetch_prices(tickers: list[str]) -> dict[str, float]:
    import yfinance as yf

    prices = {}
    for t in tickers:
        try:
            prices[t] = yf.Ticker(t).fast_info.last_price
        except Exception as e:
            print(f"WARN price fetch failed for {t}: {e}", file=sys.stderr)
    return prices


def notify(title: str, body: str) -> None:
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{body}" with title "{title}"'],
            check=False, capture_output=True,
        )
    except FileNotFoundError:
        pass  # not macOS


def check_once() -> int:
    portfolio = json.loads(PORTFOLIO.read_text())
    if not portfolio["positions"]:
        print("no open positions")
        return 0
    prices = fetch_prices([p["ticker"] for p in portfolio["positions"]])
    breaches = find_breaches(portfolio["positions"], prices)
    now_iso = datetime.now(timezone.utc).isoformat()
    for pos in breaches:
        closed = execute_stop_exit(portfolio, pos, now_iso)
        msg = (f"STOP HIT: {closed['ticker']} closed at ${closed['exit_price']} "
               f"({closed['pnl_usd']:+.2f} USD, {closed['pnl_pct']:+.1f}%) [SIMULATED]")
        print(msg)
        notify("Trade Agent — stop executed", msg)
    if breaches:
        PORTFOLIO.write_text(json.dumps(portfolio, indent=2))
    else:
        marks = ", ".join(
            f"{p['ticker']} ${prices.get(p['ticker'], 0):.2f} (stop {p['stop']})"
            for p in portfolio["positions"])
        print(f"all stops intact: {marks}")
    return len(breaches)


def loop(interval_s: int = 180) -> None:
    print(f"monitor loop started, every {interval_s}s during market hours")
    while True:
        HEARTBEAT.write_text(datetime.now(timezone.utc).isoformat())
        if market_is_open(datetime.now(ET)):
            try:
                check_once()
            except Exception as e:
                print(f"ERROR in check: {e}", file=sys.stderr)
                notify("Trade Agent — monitor error", str(e)[:120])
        time.sleep(interval_s)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "once"
    if mode == "loop":
        loop()
    else:
        sys.exit(0 if check_once() >= 0 else 1)
