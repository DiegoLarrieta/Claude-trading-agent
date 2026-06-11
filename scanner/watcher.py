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
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scanner"))

from monitor import check_once as check_stops, market_is_open, notify, session_should_run  # noqa: E402
from scan import run_scan  # noqa: E402

ET = ZoneInfo("America/New_York")
INBOX = ROOT / "candidates" / "inbox" / "pending.jsonl"
HEARTBEAT = ROOT / "journal" / ".watcher-heartbeat"

TICK_SECONDS = 60
MONITOR_INTERVAL = 180


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


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config" / "scanner.yaml").read_text())
    scan_interval = cfg["poll_interval_seconds"]
    INBOX.parent.mkdir(parents=True, exist_ok=True)
    if not INBOX.exists():
        INBOX.write_text("")
    if not session_should_run(datetime.now(ET)):
        print("market closed — watcher not needed; exiting (market-hours daemon policy)")
        return
    last_scan = last_monitor = 0.0
    print(f"watcher up: scan every {scan_interval}s, stops every {MONITOR_INTERVAL}s")
    while True:
        now_utc = datetime.now(timezone.utc)
        if not session_should_run(datetime.now(ET)):
            print("session over — watcher exiting until the next market open")
            return
        HEARTBEAT.write_text(now_utc.isoformat())
        if market_is_open(datetime.now(ET)):
            t = time.monotonic()
            if t - last_monitor >= MONITOR_INTERVAL:
                last_monitor = t
                try:
                    check_stops()
                except Exception as e:
                    print(f"ERROR stop check: {e}", file=sys.stderr)
                    notify("Trade Agent — watcher error", f"stop check: {str(e)[:100]}")
            if t - last_scan >= scan_interval:
                last_scan = t
                try:
                    created = run_scan()
                    if created:
                        INBOX.write_text(
                            enqueue_candidates(INBOX.read_text(), created, now_utc.isoformat()))
                        notify("Trade Agent — new candidates",
                               f"{len(created)} new candidate(s) queued for the committee")
                except Exception as e:
                    print(f"ERROR scan: {e}", file=sys.stderr)
                    notify("Trade Agent — watcher error", f"scan: {str(e)[:100]}")
        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    main()
