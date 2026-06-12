"""Unit tests for session state / pause / watchdog pure logic — no I/O."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from session_state import blind_window, parse_state, session_alert
from watcher import deadman_ping

NOW = datetime(2026, 6, 12, 15, 0, tzinfo=timezone.utc)


def _iso(minutes_ago: float) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).isoformat()


# ── parse_state ─────────────────────────────────────────────────────

def test_missing_or_garbage_state_means_no_session_promised():
    for text in (None, "", "not-json", json.dumps({"state": "partying"}), json.dumps([1])):
        assert parse_state(text)["state"] == "ended"


def test_valid_state_passes_through():
    rec = {"state": "paused", "since": _iso(10), "note": "lunch"}
    assert parse_state(json.dumps(rec)) == rec


# ── session_alert: the watchdog ─────────────────────────────────────

def test_active_session_with_fresh_heartbeat_is_quiet():
    assert session_alert({"state": "active"}, _iso(5), NOW) is None


def test_active_session_with_stale_heartbeat_alerts():
    assert session_alert({"state": "active"}, _iso(20), NOW) is not None


def test_active_session_with_no_heartbeat_alerts():
    assert session_alert({"state": "active"}, None, NOW) is not None
    assert session_alert({"state": "active"}, "garbage", NOW) is not None


def test_paused_and_ended_sessions_never_alert():
    for state in ("paused", "ended"):
        assert session_alert({"state": state}, _iso(500), NOW) is None
        assert session_alert({"state": state}, None, NOW) is None


# ── blind_window: what resume-brief reports ─────────────────────────

def test_deliberate_pause_starts_the_window_at_the_pause():
    state = {"state": "paused", "since": _iso(30), "note": "closing laptop"}
    since, reason = blind_window(state, _iso(5), NOW)
    assert since == _iso(30) and "closing laptop" in reason


def test_unplanned_gap_falls_back_to_last_heartbeat():
    since, reason = blind_window({"state": "active"}, _iso(90), NOW)
    assert since == _iso(90) and "unplanned" in reason


def test_no_heartbeat_at_all_is_honest_about_it():
    since, reason = blind_window({"state": "ended", "since": None}, None, NOW)
    assert since is None and "assume blind" in reason


# ── deadman_ping: fire-and-forget, never crashes the tick ───────────

def test_deadman_ping_swallows_every_failure():
    def exploding_opener(url, timeout):
        raise OSError("network is a lie")
    assert deadman_ping("https://hc-ping.com/x", opener=exploding_opener) is False


def test_deadman_ping_no_url_is_a_quiet_noop():
    def must_not_be_called(url, timeout):
        raise AssertionError("opener called without a URL")
    assert deadman_ping(None, opener=must_not_be_called) is False
    assert deadman_ping("", opener=must_not_be_called) is False


def test_deadman_ping_success():
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    assert deadman_ping("https://hc-ping.com/x", opener=lambda url, timeout: FakeResponse()) is True
