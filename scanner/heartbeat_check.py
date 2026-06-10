#!/usr/bin/env python
"""Dead-watcher detector — run by launchd every 5 minutes.

If the market is open and the watcher's heartbeat is stale (>5 min),
something silently died. Notify loudly. No LLM in this file.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scanner"))

from monitor import market_is_open, notify  # noqa: E402
from watcher import heartbeat_is_stale, HEARTBEAT  # noqa: E402

ET = ZoneInfo("America/New_York")

if __name__ == "__main__":
    if not market_is_open(datetime.now(ET)):
        sys.exit(0)
    beat = HEARTBEAT.read_text().strip() if HEARTBEAT.exists() else None
    if heartbeat_is_stale(beat, datetime.now(timezone.utc)):
        msg = "Watcher heartbeat is STALE during market hours — the firm is blind. Restart the watcher."
        print(msg, file=sys.stderr)
        notify("Trade Agent — WATCHER DOWN", msg)
        sys.exit(1)
    print("heartbeat ok")
