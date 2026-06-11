#!/usr/bin/env python
"""Deterministic trade-proposal validator — the law, enforced in code.

Every proposal the head trader writes must pass this BEFORE it is shown
to the human. It catches what day one proved LLMs get wrong (stops above
entries, stale price levels) and re-derives every limit from
config/limits.yaml and journal/portfolio.json — never trusting memos.

Usage:
  validate_proposal.py --ticker X --side buy --shares N --limit L --stop S \
      [--horizon day|swing|core] [--live-price P]
Exit 0 = VALID. Exit 1 = violations printed, one per line, prefixed VIOLATION.
No LLM anywhere in this file.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HORIZONS = ("day", "swing", "core")


# ── pure logic (unit-tested, no I/O) ────────────────────────────────


def validate(proposal: dict, portfolio: dict, limits: dict,
             live_price: float | None = None,
             now: datetime | None = None) -> list[str]:
    """Return a list of violation strings; empty list means VALID.

    Checks are independent — all violations are reported, not just the first.
    """
    v = []
    now = now or datetime.now(timezone.utc)
    ticker = proposal["ticker"].upper()
    side = proposal["side"]
    shares = proposal["shares"]
    limit_price = proposal["limit"]
    stop = proposal["stop"]

    # the master switches
    if limits.get("kill_switch"):
        v.append("kill_switch is ON — no orders of any kind")
    if side != "buy" and not limits.get("allow_short_selling"):
        v.append(f"side {side!r} — short selling is not allowed")
    if ticker in (limits.get("ticker_blacklist") or []):
        v.append(f"{ticker} is blacklisted")

    # basic sanity
    if shares <= 0:
        v.append(f"shares must be positive (got {shares})")
    if limit_price <= 0:
        v.append(f"limit price must be positive (got {limit_price})")
    if shares != int(shares) and not limits.get("allow_fractional_shares"):
        v.append(f"fractional shares ({shares}) not allowed")

    # ── stop geometry: the day-one lesson, in code forever ──
    if side == "buy":
        if stop >= limit_price:
            v.append(
                f"stop {stop} is at/above entry {limit_price} — a long would be "
                "stopped out before the fill (stale pre-gap levels?)"
            )
        elif stop < limit_price * 0.70:
            v.append(
                f"stop {stop} is more than 30% below entry {limit_price} — "
                "not a real stop, just a donation schedule"
            )

    # sizing
    cost = shares * limit_price
    if cost > limits["trade_size_usd"] * 1.02:  # 2% tolerance for rounding
        v.append(
            f"position cost ${cost:.2f} exceeds trade_size_usd "
            f"${limits['trade_size_usd']} (propose LESS, never more)"
        )
    if cost > portfolio["cash_usd"]:
        v.append(f"cost ${cost:.2f} exceeds available cash ${portfolio['cash_usd']:.2f}")

    # portfolio-level caps, re-derived from the journal
    open_positions = portfolio.get("positions", [])
    if len(open_positions) + 1 > limits["max_open_positions"]:
        v.append(
            f"already {len(open_positions)} open positions — "
            f"max_open_positions is {limits['max_open_positions']}"
        )
    if any(p["ticker"] == ticker for p in open_positions):
        v.append(f"already holding {ticker} — no adding to positions in Stage 0")

    today = now.date().isoformat()
    opened_today = [p for p in open_positions if p.get("opened_at", "").startswith(today)]
    closed_today = [t for t in portfolio.get("closed_trades", [])
                    if t.get("opened_at", "").startswith(today)]
    trades_today = len(opened_today) + len(closed_today)
    if trades_today + 1 > limits["max_trades_per_day"]:
        v.append(
            f"already {trades_today} trades today — "
            f"max_trades_per_day is {limits['max_trades_per_day']}"
        )

    exposure = sum(p["shares"] * p["fill_price"] for p in open_positions)
    if exposure + cost > limits["max_total_exposure_usd"]:
        v.append(
            f"exposure ${exposure:.2f} + ${cost:.2f} breaches "
            f"max_total_exposure_usd ${limits['max_total_exposure_usd']}"
        )

    # freshness: the proposal must be priced off the live market
    if live_price is not None:
        drift = abs(live_price - limit_price) / live_price * 100
        if drift > limits["max_price_drift_pct"]:
            v.append(
                f"limit {limit_price} is {drift:.1f}% from live price "
                f"{live_price} — max drift {limits['max_price_drift_pct']}% "
                "(stale numbers; re-run the analysis)"
            )

    horizon = proposal.get("horizon", "swing")
    if horizon not in HORIZONS:
        v.append(f"horizon {horizon!r} must be one of {HORIZONS}")

    return v


# ── I/O shell ───────────────────────────────────────────────────────


def main() -> int:
    import yaml

    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--side", default="buy")
    ap.add_argument("--shares", type=float, required=True)
    ap.add_argument("--limit", type=float, required=True)
    ap.add_argument("--stop", type=float, required=True)
    ap.add_argument("--horizon", default="swing")
    ap.add_argument("--live-price", type=float, default=None,
                    help="omit to fetch from yfinance")
    args = ap.parse_args()

    limits = yaml.safe_load((ROOT / "config" / "limits.yaml").read_text())
    portfolio = json.loads((ROOT / "journal" / "portfolio.json").read_text())

    live = args.live_price
    if live is None:
        try:
            import yfinance as yf
            live = yf.Ticker(args.ticker).fast_info.last_price
        except Exception as e:
            print(f"WARN live price unavailable ({e}) — drift check skipped",
                  file=sys.stderr)

    proposal = {"ticker": args.ticker, "side": args.side, "shares": args.shares,
                "limit": args.limit, "stop": args.stop, "horizon": args.horizon}
    violations = validate(proposal, portfolio, limits, live_price=live)
    if violations:
        for x in violations:
            print(f"VIOLATION: {x}")
        return 1
    print(f"VALID: {args.ticker} {args.side} {args.shares} @ {args.limit} "
          f"stop {args.stop} horizon {args.horizon}"
          + (f" (live ${live:.2f})" if live else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
