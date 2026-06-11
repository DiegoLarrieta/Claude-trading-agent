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


def execute_stop_exit(portfolio: dict, position: dict, now_iso: str,
                      live_price: float | None = None) -> dict:
    """Close a breached position. Returns the closed-trade record.

    Honest fill assumption: a stop order becomes a market order at the
    stop level, so the fill is the WORSE of stop and live price. If the
    price gapped below the stop, you get the gapped price — pretending
    otherwise flatters the simulation.
    """
    exit_price = position["stop"]
    exit_reason = "stop"
    if live_price is not None and live_price < exit_price:
        exit_price = live_price
        exit_reason = "stop_gap"
    proceeds = round(position["shares"] * exit_price, 2)
    cost = round(position["shares"] * position["fill_price"], 2)
    closed = {
        **position,
        "closed_at": now_iso,
        "exit_price": round(exit_price, 4),
        "exit_reason": exit_reason,
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


def rules_for(position: dict, exits: dict) -> dict | None:
    """Pick the exit profile matching the position's horizon.

    exits may be per-horizon ({day: {...}, swing: {...}, core: {...}}) or
    the legacy flat form ({breakeven_trigger_pct: ...}), which applies to
    everything. Untagged positions are 'swing'. Unknown horizon = no rules
    (never guess which escalation policy to apply to someone's position).
    """
    if "breakeven_trigger_pct" in exits:
        return exits
    return exits.get(position.get("horizon", "swing"))


def adjust_stops(positions: list[dict], prices: dict[str, float], exits: dict) -> list[dict]:
    """Mechanical stop management. Returns positions whose stop was RAISED.

    Each position is escalated by its own horizon's profile (see rules_for):
    - breakeven: at +breakeven_trigger_pct, stop rises to entry price
    - trailing:  at +trail_trigger_pct, stop trails trail_distance_pct
                 below the highest price seen (tracked as 'high_water')
    Stops only ever move UP. No rule ever widens a stop. Missing price = no change.
    """
    changed = []
    for pos in positions:
        price = prices.get(pos["ticker"])
        if price is None or pos["side"] != "buy":
            continue
        rules = rules_for(pos, exits)
        if rules is None:
            continue
        entry = pos["fill_price"]
        pos["high_water"] = max(pos.get("high_water", entry), price)
        gain_pct = (price - entry) / entry * 100
        candidates = [pos["stop"]]
        if gain_pct >= rules["breakeven_trigger_pct"]:
            candidates.append(entry)
        if gain_pct >= rules["trail_trigger_pct"]:
            candidates.append(pos["high_water"] * (1 - rules["trail_distance_pct"] / 100))
        new_stop = round(max(candidates), 2)
        if new_stop > pos["stop"]:
            pos["prior_stop"] = pos["stop"]
            pos["stop"] = new_stop
            # notify only on MEANINGFUL raises (>=0.5% above the last one we
            # announced) — a trending stock raises its trail every tick, and
            # ten pings for ten cents teaches the human to ignore alerts.
            last_announced = pos.get("last_announced_stop")
            pos["notify"] = (last_announced is None
                             or new_stop >= last_announced * 1.005)
            if pos["notify"]:
                pos["last_announced_stop"] = new_stop
            changed.append(pos)
    return changed


def market_is_open(now_et: datetime) -> bool:
    if now_et.weekday() >= 5:
        return False
    minutes = now_et.hour * 60 + now_et.minute
    return (9 * 60 + 30) <= minutes < (16 * 60)


def session_should_run(now_et: datetime, pre_open_min: int = 20, post_close_min: int = 5) -> bool:
    """Whether the firm's daemons should be alive right now.

    Market hours plus a pre-open grace (so a daemon launched at 9:25 waits
    for the bell instead of exiting) and a short post-close grace (so the
    final stop check sees closing prices). Outside this window daemons
    self-terminate — nothing runs overnight or on weekends, by policy.
    """
    if now_et.weekday() >= 5:
        return False
    minutes = now_et.hour * 60 + now_et.minute
    return (9 * 60 + 30 - pre_open_min) <= minutes < (16 * 60 + post_close_min)


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
    try:  # best-effort Telegram mirror; no-op until token + chat id configured
        from telegram_bot import send_alert
        send_alert(f"{title}\n{body}")
    except Exception:
        pass


def check_once() -> int:
    import yaml

    portfolio = json.loads(PORTFOLIO.read_text())
    if not portfolio["positions"]:
        print("no open positions")
        return 0
    prices = fetch_prices([p["ticker"] for p in portfolio["positions"]])

    # 1) mechanical stop management (raise-only) BEFORE breach detection
    exit_rules = yaml.safe_load((ROOT / "config" / "limits.yaml").read_text()).get("exits")
    raised = adjust_stops(portfolio["positions"], prices, exit_rules) if exit_rules else []
    for pos in raised:
        msg = (f"STOP RAISED: {pos['ticker']} {pos['prior_stop']} → {pos['stop']} "
               f"(price ${prices[pos['ticker']]:.2f}) [{'breakeven' if pos['stop'] <= pos['fill_price'] else 'trailing'}]")
        print(msg)
        if pos.pop("notify", True):
            notify("Trade Agent — stop raised", msg)

    # 2) breach detection at (possibly raised) stops
    breaches = find_breaches(portfolio["positions"], prices)
    now_iso = datetime.now(timezone.utc).isoformat()
    for pos in breaches:
        closed = execute_stop_exit(portfolio, pos, now_iso, live_price=prices.get(pos["ticker"]))
        msg = (f"STOP HIT: {closed['ticker']} closed at ${closed['exit_price']} "
               f"({closed['pnl_usd']:+.2f} USD, {closed['pnl_pct']:+.1f}%) [SIMULATED]")
        print(msg)
        notify("Trade Agent — stop executed", msg)
    if breaches or raised:
        PORTFOLIO.write_text(json.dumps(portfolio, indent=2))
    if not breaches:
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
