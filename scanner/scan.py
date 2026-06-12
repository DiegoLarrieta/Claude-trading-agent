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
UNIVERSE_FILE = ROOT / "config" / "universe.yaml"
UNIVERSE = yaml.safe_load(UNIVERSE_FILE.read_text()) if UNIVERSE_FILE.exists() else {}

ET = ZoneInfo("America/New_York")


def _now_et() -> datetime:
    """Wall clock per call. The watcher imports this module once before the
    open and calls run_scan() all session — a module-level timestamp froze
    the clock (2026-06-12: every folder carried the import-time HHMM stamp
    and volume proration divided by minute 1 all morning, inflating
    multiples ~390x)."""
    return datetime.now(ET)


now_et = _now_et()  # import-time snapshot: only for one-shot CLI helpers
today = now_et.strftime("%Y-%m-%d")
day_dir = ROOT / "candidates" / today
day_dir.mkdir(parents=True, exist_ok=True)


def theme_of(ticker: str, universe: dict) -> str | None:
    """Return the theme a ticker belongs to, or None if not on the watchlist."""
    for theme, tickers in (universe.get("themes") or {}).items():
        if ticker in tickers:
            return theme
    return None


def triggers_for(ticker: str, universe: dict, base: dict) -> dict:
    """Watchlist names use the (more sensitive) watchlist thresholds."""
    if theme_of(ticker, universe) and universe.get("watchlist_triggers"):
        return {**base, **universe["watchlist_triggers"]}
    return base


def days_to_earnings(earnings_dates: list, today) -> int | None:
    """Days until the next earnings date on/after today; None if unknown."""
    future = [(d - today).days for d in earnings_dates if d >= today]
    return min(future) if future else None


def in_cooldown(ticker: str) -> bool:
    cooldown_min = CFG["cooldown_minutes"]
    now = _now_et()
    for folder in day_dir.glob(f"{ticker}-*"):
        try:
            hhmm = folder.name.rsplit("-", 1)[1]
            created = now.replace(hour=int(hhmm[:2]), minute=int(hhmm[2:]), second=0)
            if (now - created).total_seconds() < cooldown_min * 60:
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


def triggers_fired(q, trig=None):
    trig = trig or CFG["triggers"]
    fired = []
    pct = q.get("regularMarketChangePercent") or 0.0
    if abs(pct) >= trig["pct_move_intraday"]:
        fired.append("pct_move")
    vol = q.get("regularMarketVolume") or 0
    avg_vol = q.get("averageDailyVolume3Month") or 0
    # prorate: compare today's running volume to the same fraction of an avg day
    now = _now_et()
    mins_open = max(1, min(390, (now.hour * 60 + now.minute) - (9 * 60 + 30)))
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


def pre_triage_kill(pct: float, days_to_earn: int | None, watchlist: bool,
                    trig_pct: float, cfg: dict) -> str | None:
    """Deterministic kills that used to cost an LLM triage call.

    Returns the kill reason, or None to let the candidate through. Only
    rules with a mechanical answer belong here — anything needing judgment
    stays with the triage analyst. Killed candidates create no folder and
    consume no daily budget.
    """
    if not cfg:
        return None
    window = cfg.get("earnings_window_days", 1)
    mult = cfg.get("extraordinary_pct_multiple", 2.0)
    if (days_to_earn is not None and days_to_earn <= window
            and not watchlist and abs(pct) < trig_pct * mult):
        return (f"earnings reaction (T-{days_to_earn}): explained move, "
                f"{pct:+.1f}% under the {trig_pct * mult:.0f}% extraordinary bar")
    return None


def effective_daily_cap(hour_et: float, max_per_day: int, cfg: dict | None) -> int:
    """Time-bucketed daily budget: hold back a slice of the daily candidate
    allowance for the afternoon so the opening flood can't blind the scanner
    for the rest of the session (2026-06-12: all 60 daily slots spent by
    mid-morning; SNDK +5.7% and ANET +5.2% ran invisible until the user
    nominated them by hand). Before release_at_hour_et the cap is
    max_per_day minus the reserve; after it, the full allowance applies.
    """
    if not cfg:
        return max_per_day
    reserve = int(cfg.get("afternoon_candidates", 0))
    release = float(cfg.get("release_at_hour_et", 12.0))
    if hour_et < release:
        return max(0, max_per_day - reserve)
    return max_per_day


def budget_alerts(existing_today: int, max_per_day: int, announced: list[int]) -> list[int]:
    """Daily-budget thresholds (as % of max) newly crossed and not yet announced.

    A silent scanner is indistinguishable from a quiet market (lesson #7,
    2026-06-11: blind from 9:50am while MU/SNDK/ANET ran). Each threshold
    fires once per day.
    """
    crossed = []
    for pct in (80, 100):
        if pct in announced:
            continue
        if existing_today >= max_per_day * pct / 100:
            crossed.append(pct)
    return crossed


def fetch_watchlist_quotes(tickers: list[str]) -> list[dict]:
    """Quote the thesis universe directly — watchlist names rarely make the
    top-movers screeners, so they get their own sweep."""
    quotes = []
    for sym in tickers:
        try:
            fi = yf.Ticker(sym).fast_info
            prev = fi.previous_close
            quotes.append({
                "symbol": sym,
                "regularMarketPrice": fi.last_price,
                "regularMarketPreviousClose": prev,
                "regularMarketChangePercent": (fi.last_price - prev) / prev * 100 if prev else 0,
                "regularMarketVolume": fi.last_volume,
                "averageDailyVolume3Month": fi.three_month_average_volume,
                "marketCap": fi.market_cap,
                "fiftyTwoWeekLow": fi.year_low,
                "fiftyTwoWeekHigh": fi.year_high,
            })
        except Exception as e:
            print(f"WARN watchlist quote failed for {sym}: {e}", file=sys.stderr)
    return quotes


def fetch_days_to_earnings(ticker: str) -> int | None:
    try:
        dates = (yf.Ticker(ticker).calendar or {}).get("Earnings Date") or []
        return days_to_earnings(dates, _now_et().date())
    except Exception as e:
        print(f"WARN earnings calendar failed for {ticker}: {e}", file=sys.stderr)
        return None


def run_scan() -> list[str]:
    """Run one scan pass; returns list of created candidate folder paths."""
    movers = fetch_movers()
    watch_tickers = [t for theme in (UNIVERSE.get("themes") or {}).values() for t in theme]
    screener_syms = {q["symbol"] for q in movers}
    movers += fetch_watchlist_quotes([t for t in watch_tickers if t not in screener_syms])
    existing_today = len(list(day_dir.glob("*-*")))
    # three-level budget: a per-scan cap stops the opening flood from eating
    # the whole daily allowance, and an afternoon reserve keeps slots back
    # so the scanner stays sighted into the close
    now = _now_et()
    cap = effective_daily_cap(now.hour + now.minute / 60,
                              CFG["max_candidates_per_day"],
                              CFG.get("budget_reserve"))
    budget = min(CFG.get("max_candidates_per_scan", 8), cap - existing_today)
    created = []
    for q in movers:
        if budget <= 0:
            break
        sym = q["symbol"]
        theme = theme_of(sym, UNIVERSE)
        if not passes_universe(q):
            continue
        trig = triggers_for(sym, UNIVERSE, CFG["triggers"])
        fired, pct, vol_mult = triggers_fired(q, trig)
        if not fired:
            continue
        if in_cooldown(sym):
            continue
        days_te = fetch_days_to_earnings(sym)
        kill = pre_triage_kill(pct, days_te, bool(theme),
                               trig["pct_move_intraday"], CFG.get("pre_triage") or {})
        if kill:
            print(f"  pre-triage KILL {sym}: {kill}")
            continue
        folder = day_dir / f"{sym}-{_now_et().strftime('%H%M')}"
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
            "watchlist": bool(theme),
            "theme": theme,
            "days_to_earnings": days_te,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "scanner_notes": f"52w range {q.get('fiftyTwoWeekLow')}–{q.get('fiftyTwoWeekHigh')}",
        }
        (folder / "candidate.json").write_text(json.dumps(cand, indent=2))
        created.append(str(folder))
        tag = f" [watchlist:{theme}]" if theme else ""
        print(f"  {sym} {pct:+.1f}% vol×{vol_mult} [{'+'.join(fired)}]{tag}")
        budget -= 1
    print(f"{len(created)} candidate(s) created")
    return created


if __name__ == "__main__":
    run_scan()
