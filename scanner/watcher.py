#!/usr/bin/env python
"""The watcher daemon — the firm's always-on eyes. No LLM in this file.

One background process that, during market hours:
  - scans the market every `poll_interval_seconds` (config/scanner.yaml)
    and queues new candidates into candidates/inbox/pending.jsonl
  - checks position stops every MONITOR_INTERVAL seconds (monitor.py)
  - writes a heartbeat file every tick so silence is detectable

Run under launchd (ops/install-watcher.sh) or manually:
  .venv/bin/python scanner/watcher.py
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scanner"))

from inbox_queue import latest_statuses, oldest_unprocessed_age_minutes, parse_jsonl  # noqa: E402
from monitor import check_once as check_stops, market_is_open, notify, session_should_run  # noqa: E402
from scan import budget_alerts, run_scan  # noqa: E402

ET = ZoneInfo("America/New_York")
INBOX = ROOT / "candidates" / "inbox" / "pending.jsonl"
PROCESSED = ROOT / "candidates" / "inbox" / "processed.jsonl"
HEARTBEAT = ROOT / "journal" / ".watcher-heartbeat"
BUDGET_STATE = ROOT / "journal" / ".scanner-budget-alerts.json"

TICK_SECONDS = 60
MONITOR_INTERVAL = 180
BACKLOG_ALERT_COOLDOWN = 3600  # repeat the rotting-queue alarm at most hourly


# ── pure logic (unit-tested) ────────────────────────────────────────


def enqueue_candidates(inbox_text: str, folders: list[str], now_iso: str) -> str:
    """Append new candidate folders to the inbox, skipping ones already queued.

    The inbox is a JSONL file the interactive Claude session consumes;
    each line: {"folder": ..., "queued_at": ..., "status": "pending"}.
    """
    known = set()
    for line in inbox_text.splitlines():
        try:
            known.add(json.loads(line)["folder"])
        except (json.JSONDecodeError, KeyError):
            continue
    out = inbox_text
    for folder in folders:
        if folder in known:
            continue
        out += json.dumps({"folder": folder, "queued_at": now_iso, "status": "pending"}) + "\n"
    return out


def candidate_alert_text(cands: list[dict], limit: int = 8) -> str:
    """One line per candidate for the Telegram alert — ticker, move, volume.

    A bare count ("8 new candidate(s)") tells the human nothing actionable
    (Diego, 2026-06-12); the tickers do. Unreadable candidate.json entries
    degrade to the folder name rather than dropping the line.
    """
    lines = []
    for c in cands[:limit]:
        ticker = c.get("ticker") or Path(c.get("folder", "?")).name
        pct = c.get("pct_move")
        vol = c.get("volume_multiple")
        detail = f"{pct:+.1f}%" if isinstance(pct, (int, float)) else "?%"
        if isinstance(vol, (int, float)):
            detail += f" vol×{vol}"
        lines.append(f"{ticker} {detail}")
    if len(cands) > limit:
        lines.append(f"…and {len(cands) - limit} more")
    return "\n".join(lines)


def heartbeat_is_stale(heartbeat_iso: str | None, now: datetime, max_age_s: int = 300) -> bool:
    """True if the heartbeat is missing or older than max_age_s."""
    if not heartbeat_iso:
        return True
    try:
        beat = datetime.fromisoformat(heartbeat_iso)
    except ValueError:
        return True
    return (now - beat).total_seconds() > max_age_s


# ── daemon shell ────────────────────────────────────────────────────


def deadman_ping(url: str | None, opener=urllib.request.urlopen) -> bool:
    """Ping the external dead-man switch (healthchecks.io). Fire-and-forget:
    NOTHING that happens here may crash the tick — a monitoring outage must
    never take down the thing it monitors. Returns whether the ping landed."""
    if not url:
        return False
    try:
        with opener(url, timeout=5):
            return True
    except Exception:
        return False


def deadman_url() -> str | None:
    """DEADMAN_PING_URL from .env (gitignored, same home as the Telegram token)."""
    try:
        from telegram_bot import ENV_FILE, parse_env
        env = parse_env(ENV_FILE.read_text()) if ENV_FILE.exists() else {}
        return env.get("DEADMAN_PING_URL") or None
    except Exception:
        return None


def stay_awake() -> None:
    """Keep the Mac from idle-sleeping while the watcher lives (macOS only).

    caffeinate -w dies with us, so the assertion never outlives the daemon.
    A closed lid still sleeps the machine — that gap belongs to the external
    dead-man switch, not to caffeinate.
    """
    try:
        subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("caffeinate engaged: no idle sleep while the watcher runs")
    except (FileNotFoundError, OSError):
        pass  # not macOS — nothing to do


def check_budget(cfg: dict, today: str) -> None:
    """Alert at 80% and 100% of the daily candidate budget, once each per day."""
    state = {"date": today, "announced": []}
    if BUDGET_STATE.exists():
        try:
            loaded = json.loads(BUDGET_STATE.read_text())
            if loaded.get("date") == today:
                state = loaded
        except json.JSONDecodeError:
            pass
    existing = len(list((ROOT / "candidates" / today).glob("*-*")))
    max_per_day = cfg["max_candidates_per_day"]
    for pct in budget_alerts(existing, max_per_day, state["announced"]):
        if pct >= 100:
            notify("Trade Agent — SCANNER BLIND",
                   f"daily candidate budget exhausted ({existing}/{max_per_day}) — "
                   "no new candidates until tomorrow unless the cap is raised")
        else:
            notify("Trade Agent — scanner budget warning",
                   f"{pct}% of daily candidate budget used ({existing}/{max_per_day})")
        state["announced"].append(pct)
    BUDGET_STATE.write_text(json.dumps(state))


def check_backlog(now_utc: datetime, queue_cfg: dict) -> str | None:
    """Message if the oldest untouched candidate exceeds the backlog limit."""
    entries = parse_jsonl(INBOX.read_text() if INBOX.exists() else "")
    statuses = latest_statuses(parse_jsonl(PROCESSED.read_text() if PROCESSED.exists() else ""))
    age = oldest_unprocessed_age_minutes(entries, statuses, now_utc)
    limit = queue_cfg.get("backlog_alert_minutes", 45)
    if age is not None and age > limit:
        return (f"oldest queued candidate untouched for {age:.0f} min "
                f"(limit {limit}) — is the committee session running?")
    return None


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config" / "scanner.yaml").read_text())
    scan_interval = cfg["poll_interval_seconds"]
    INBOX.parent.mkdir(parents=True, exist_ok=True)
    if not INBOX.exists():
        INBOX.write_text("")
    if not session_should_run(datetime.now(ET)):
        print("market closed — watcher not needed; exiting (market-hours daemon policy)")
        return
    stay_awake()
    ping_url = deadman_url()
    print(f"dead-man switch: {'configured' if ping_url else 'NOT configured (DEADMAN_PING_URL in .env)'}")
    last_scan = last_monitor = 0.0
    last_backlog_alert = -BACKLOG_ALERT_COOLDOWN  # eligible immediately
    print(f"watcher up: scan every {scan_interval}s, stops every {MONITOR_INTERVAL}s")
    while True:
        now_utc = datetime.now(timezone.utc)
        if not session_should_run(datetime.now(ET)):
            print("session over — watcher exiting until the next market open")
            return
        HEARTBEAT.write_text(now_utc.isoformat())
        deadman_ping(ping_url)
        if market_is_open(datetime.now(ET)):
            t = time.monotonic()
            if t - last_monitor >= MONITOR_INTERVAL:
                last_monitor = t
                try:
                    check_stops()
                except Exception as e:
                    print(f"ERROR stop check: {e}", file=sys.stderr)
                    notify("Trade Agent — watcher error", f"stop check: {str(e)[:100]}")
                try:
                    from watch_levels import check_once as check_watch_levels
                    check_watch_levels()
                except Exception as e:
                    print(f"ERROR watch levels: {e}", file=sys.stderr)
                    notify("Trade Agent — watcher error", f"watch levels: {str(e)[:100]}")
                try:
                    msg = check_backlog(now_utc, cfg.get("queue") or {})
                    if msg and t - last_backlog_alert >= BACKLOG_ALERT_COOLDOWN:
                        last_backlog_alert = t
                        print(f"BACKLOG: {msg}")
                        notify("Trade Agent — queue backlog", msg)
                except Exception as e:
                    print(f"ERROR backlog check: {e}", file=sys.stderr)
            if t - last_scan >= scan_interval:
                last_scan = t
                try:
                    created = run_scan()
                    if created:
                        INBOX.write_text(
                            enqueue_candidates(INBOX.read_text(), created, now_utc.isoformat()))
                        cands = []
                        for folder in created:
                            try:
                                cand = json.loads(
                                    (Path(folder) / "candidate.json").read_text())
                            except (OSError, json.JSONDecodeError):
                                cand = {}
                            cands.append({**cand, "folder": folder})
                        notify("Trade Agent — new candidates",
                               f"{len(created)} queued for the committee:\n"
                               + candidate_alert_text(cands))
                    check_budget(cfg, datetime.now(ET).strftime("%Y-%m-%d"))
                except Exception as e:
                    print(f"ERROR scan: {e}", file=sys.stderr)
                    notify("Trade Agent — watcher error", f"scan: {str(e)[:100]}")
        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    main()
