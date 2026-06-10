#!/usr/bin/env python
"""Deterministic market scanner — Stage 0/2 core.

Pulls today's top movers from Yahoo screeners, filters by the universe
rules in config/scanner.yaml, checks trigger thresholds, and emits
candidate folders under candidates/YYYY-MM-DD/TICKER-HHMM/candidate.json.
No LLM anywhere in this file.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((ROOT / "config" / "scanner.yaml").read_text())
LIMITS = yaml.safe_load((ROOT / "config" / "limits.yaml").read_text())

ET = ZoneInfo("America/New_York")
now_et = datetime.now(ET)
today = now_et.strftime("%Y-%m-%d")
day_dir = ROOT / "candidates" / today
day_dir.mkdir(parents=True, exist_ok=True)


def in_cooldown(ticker: str) -> bool:
    cooldown_min = CFG["cooldown_minutes"]
    for folder in day_dir.glob(f"{ticker}-*"):
        try:
            hhmm = folder.name.rsplit("-", 1)[1]
            created = now_et.replace(hour=int(hhmm[:2]), minute=int(hhmm[2:]), second=0)
            if (now_et - created).total_seconds() < cooldown_min * 60:
                return True
        except (ValueError, IndexError):
            return True  # unparseable folder for this ticker today -> be safe
    return False


def fetch_movers():
    rows = []
    for screen in ("day_gainers", "day_losers", "most_actives"):
        try:
            res = yf.screen(screen, count=25)
            rows += res.get("quotes", [])
        except Exception as e:
            print(f"WARN screener {screen} failed: {e}", file=sys.stderr)
    seen, out = set(), []
    for q in rows:
        sym = q.get("symbol")
        if sym and sym not in seen:
            seen.add(sym)
            out.append(q)
    return out


def passes_universe(q) -> bool:
    uni = CFG["universe"]
    if (q.get("marketCap") or 0) < uni["min_market_cap_usd"]:
        return False
    price = q.get("regularMarketPrice") or 0
    vol = q.get("regularMarketVolume") or 0
    if price * vol < uni["min_avg_dollar_volume"]:
        return False
    if q.get("fullExchangeName", "").upper().startswith(("OTC", "PINK")):
        return False
    name = (q.get("shortName") or "").lower()
    if uni.get("exclude_leveraged_etfs") and any(
        k in name for k in ("2x", "3x", "ultra", "leveraged", "bull", "bear etf")
    ):
        return False
    if q.get("symbol") in (LIMITS.get("ticker_blacklist") or []):
        return False
    return True


def triggers_fired(q):
    trig = CFG["triggers"]
    fired = []
    pct = q.get("regularMarketChangePercent") or 0.0
    if abs(pct) >= trig["pct_move_intraday"]:
        fired.append("pct_move")
    vol = q.get("regularMarketVolume") or 0
    avg_vol = q.get("averageDailyVolume3Month") or 0
    # prorate: compare today's running volume to the same fraction of an avg day
    mins_open = max(1, min(390, (now_et.hour * 60 + now_et.minute) - (9 * 60 + 30)))
    expected_by_now = avg_vol * (mins_open / 390)
    vol_mult = vol / expected_by_now if expected_by_now else 0
    if vol_mult >= trig["volume_multiple"]:
        fired.append("volume")
    lo, hi = q.get("fiftyTwoWeekLow"), q.get("fiftyTwoWeekHigh")
    price = q.get("regularMarketPrice")
    if trig.get("week52_extreme") and price and lo and hi:
        if price <= lo * 1.005 or price >= hi * 0.995:
            fired.append("52w")
    return fired, pct, round(vol_mult, 1)


def main():
    movers = fetch_movers()
    existing_today = len(list(day_dir.glob("*-*")))
    budget = CFG["max_candidates_per_day"] - existing_today
    created = []
    for q in movers:
        if budget <= 0:
            break
        if not passes_universe(q):
            continue
        fired, pct, vol_mult = triggers_fired(q)
        if not fired:
            continue
        sym = q["symbol"]
        if in_cooldown(sym):
            continue
        folder = day_dir / f"{sym}-{now_et.strftime('%H%M')}"
        folder.mkdir(exist_ok=True)
        cand = {
            "ticker": sym,
            "name": q.get("shortName"),
            "trigger": "+".join(fired),
            "pct_move": round(pct, 2),
            "volume_multiple": vol_mult,
            "price": q.get("regularMarketPrice"),
            "prev_close": q.get("regularMarketPreviousClose"),
            "market_cap": q.get("marketCap"),
            "exchange": q.get("fullExchangeName"),
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "scanner_notes": f"52w range {q.get('fiftyTwoWeekLow')}–{q.get('fiftyTwoWeekHigh')}",
        }
        (folder / "candidate.json").write_text(json.dumps(cand, indent=2))
        created.append(f"{sym} {pct:+.1f}% vol×{vol_mult} [{'+'.join(fired)}]")
        budget -= 1
    print(f"{len(created)} candidate(s) created:")
    for line in created:
        print(" ", line)


if __name__ == "__main__":
    main()
