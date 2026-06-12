#!/usr/bin/env python
"""Session state + session heartbeat — how the firm knows the LLM side is alive.

The watcher daemon guards stops no matter what. This file tracks the OTHER
half: the interactive Claude session that runs committees. It promises
presence ("active"), declares deliberate blindness ("paused"), or signs
off ("ended"). heartbeat_check.py alerts when an *active* session's
heartbeat goes stale — a wedged or usage-locked session must become loud,
not silently dark.

  journal/.session-state.json   {"state": "active|paused|ended", "since": ISO, "note": ...}
  journal/.session-heartbeat    ISO timestamp, touched by the session each tick

CLI (used by /pause, /trading-day, /market-loop):
  session_state.py set active|paused|ended [--note ...]
  session_state.py touch            # update the session heartbeat
  session_state.py get
  session_state.py resume-brief     # blind window + catch-up order after a pause/sleep
No LLM in this file.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "journal" / ".session-state.json"
SESSION_HEARTBEAT = ROOT / "journal" / ".session-heartbeat"

STATES = ("active", "paused", "ended")


# ── pure logic (unit-tested, no I/O) ────────────────────────────────


def parse_state(text: str | None) -> dict:
    """Parse the state file; anything unreadable means 'no session promised'."""
    if not text:
        return {"state": "ended", "since": None, "note": "no state file"}
    try:
        state = json.loads(text)
    except json.JSONDecodeError:
        return {"state": "ended", "since": None, "note": "unreadable state file"}
    if not isinstance(state, dict) or state.get("state") not in STATES:
        return {"state": "ended", "since": None, "note": "unreadable state file"}
    return state


def _age_minutes(iso: str | None, now: datetime) -> float | None:
    if not iso:
        return None
    try:
        return (now - datetime.fromisoformat(iso)).total_seconds() / 60
    except ValueError:
        return None


def session_alert(state: dict, heartbeat_iso: str | None, now: datetime,
                  max_age_min: float = 15) -> str | None:
    """Alert message if an ACTIVE session's heartbeat is stale, else None.

    paused/ended sessions promised nothing — never alert on them. An active
    session with no heartbeat at all is the worst case: it claimed presence
    and went dark immediately.
    """
    if state.get("state") != "active":
        return None
    age = _age_minutes(heartbeat_iso, now)
    if age is None:
        return ("Session is marked ACTIVE but has no readable heartbeat — "
                "the committee side is dark. Check the Claude session.")
    if age > max_age_min:
        return (f"Session heartbeat is {age:.0f} min old (limit {max_age_min:.0f}) — "
                "the committee session looks wedged or usage-locked. Check it.")
    return None


def blind_window(state: dict, heartbeat_iso: str | None, now: datetime) -> tuple[str | None, str]:
    """When did the LLM side go blind, and why.

    A deliberate pause starts the window at the pause; otherwise the last
    session heartbeat is the best honest estimate (crash, sleep, lid).
    Returns (since_iso_or_None, reason).
    """
    if state.get("state") == "paused" and state.get("since"):
        return state["since"], state.get("note") or "deliberate pause"
    if heartbeat_iso and _age_minutes(heartbeat_iso, now) is not None:
        return heartbeat_iso, "last session heartbeat (unplanned gap: crash/sleep/lid)"
    return None, "no heartbeat on record — assume blind since session start"


# ── I/O shell ───────────────────────────────────────────────────────


def read_state() -> dict:
    return parse_state(STATE_FILE.read_text() if STATE_FILE.exists() else None)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_set = sub.add_parser("set")
    p_set.add_argument("state", choices=STATES)
    p_set.add_argument("--note", default=None)
    sub.add_parser("touch")
    sub.add_parser("get")
    sub.add_parser("resume-brief")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)

    if args.cmd == "set":
        rec = {"state": args.state, "since": now.isoformat()}
        if args.note:
            rec["note"] = args.note
        STATE_FILE.write_text(json.dumps(rec))
        if args.state == "active":
            SESSION_HEARTBEAT.write_text(now.isoformat())
        print(f"session {args.state}")
    elif args.cmd == "touch":
        SESSION_HEARTBEAT.write_text(now.isoformat())
        print("session heartbeat updated")
    elif args.cmd == "get":
        print(json.dumps(read_state()))
    elif args.cmd == "resume-brief":
        hb = SESSION_HEARTBEAT.read_text().strip() if SESSION_HEARTBEAT.exists() else None
        since, reason = blind_window(read_state(), hb, now)
        mins = _age_minutes(since, now)
        print(f"BLIND SINCE: {since or 'unknown'} ({reason})"
              + (f" — {mins:.0f} min" if mins is not None else ""))
        print("CATCH-UP ORDER (do not skip, do not reorder):")
        print("  1. STOPS FIRST — read journal/portfolio.json, pull live prices, "
              "verify every stop; confirm the watcher heartbeat is fresh")
        print("  2. BACKLOG — .venv/bin/python scanner/inbox_queue.py pending "
              "(expired candidates get marked stale automatically)")
        print("  3. FRESH LOOK — resume the normal loop; then: "
              "session_state.py set active")
    sys.exit(0)


if __name__ == "__main__":
    main()
