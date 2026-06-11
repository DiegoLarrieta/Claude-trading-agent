"""Unit tests for the gateway-alert cooldown — no network."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from heartbeat_check import cooldown_elapsed

NOW = datetime(2026, 6, 11, 15, 0, tzinfo=timezone.utc)


def test_never_alerted_means_elapsed():
    assert cooldown_elapsed(None, NOW)


def test_recent_alert_blocks():
    assert not cooldown_elapsed("2026-06-11T14:30:00+00:00", NOW)


def test_old_alert_allows():
    assert cooldown_elapsed("2026-06-11T13:59:00+00:00", NOW)


def test_garbage_state_fails_open():
    assert cooldown_elapsed("not-a-date", NOW)
