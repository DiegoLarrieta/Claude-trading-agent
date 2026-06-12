#!/usr/bin/env python
"""Dead-watcher + dead-gateway detector — run by launchd every 5 minutes.

During market hours two things must be alive:
  1. the watcher (stop protection) — its heartbeat file must be fresh
  2. IB Gateway (broker link) — a paper port must be listening
If either is missing, notify loudly. Gateway alerts have a cooldown so a
known outage doesn't ping every 5 minutes. Outside market hours this
script exits immediately. No LLM in this file.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scanner"))

from broker import find_gateway_port  # noqa: E402
from monitor import market_is_open, notify  # noqa: E402
from session_state import SESSION_HEARTBEAT, read_state, session_alert  # noqa: E402
from watcher import heartbeat_is_stale, HEARTBEAT  # noqa: E402

ET = ZoneInfo("America/New_York")
GATEWAY_ALERT_STATE = ROOT / "journal" / ".gateway-alert-ts"


def cooldown_elapsed(last_alert_iso: str | None, now: datetime, minutes: int = 60) -> bool:
    """True if it's been long enough since the last alert (or never alerted)."""
    if not last_alert_iso:
        return True
    try:
        last = datetime.fromisoformat(last_alert_iso)
    except ValueError:
        return True
    return (now - last).total_seconds() >= minutes * 60


def check_gateway(now_utc: datetime) -> bool:
    """Alert (with cooldown) if no Gateway is listening. Returns gateway-ok."""
    if find_gateway_port() is not None:
        if GATEWAY_ALERT_STATE.exists():
            GATEWAY_ALERT_STATE.unlink()  # recovered — re-arm immediate alerting
        return True
    last = GATEWAY_ALERT_STATE.read_text().strip() if GATEWAY_ALERT_STATE.exists() else None
    if cooldown_elapsed(last, now_utc):
        msg = ("IB Gateway is DOWN during market hours — broker link dark. "
               "Open IB Gateway and log into the paper account.")
        print(msg, file=sys.stderr)
        notify("Trade Agent — GATEWAY DOWN", msg)
        GATEWAY_ALERT_STATE.write_text(now_utc.isoformat())
    return False


if __name__ == "__main__":
    if not market_is_open(datetime.now(ET)):
        sys.exit(0)
    failures = 0
    beat = HEARTBEAT.read_text().strip() if HEARTBEAT.exists() else None
    if heartbeat_is_stale(beat, datetime.now(timezone.utc)):
        msg = "Watcher heartbeat is STALE during market hours — the firm is blind. Restart the watcher."
        print(msg, file=sys.stderr)
        notify("Trade Agent — WATCHER DOWN", msg)
        failures += 1
    if not check_gateway(datetime.now(timezone.utc)):
        failures += 1
    # the committee session promised presence? hold it to that promise
    session_hb = SESSION_HEARTBEAT.read_text().strip() if SESSION_HEARTBEAT.exists() else None
    msg = session_alert(read_state(), session_hb, datetime.now(timezone.utc))
    if msg:
        print(msg, file=sys.stderr)
        notify("Trade Agent — SESSION DARK", msg)
        failures += 1
    if failures == 0:
        print("heartbeat ok, gateway ok, session accounted for")
    sys.exit(1 if failures else 0)
