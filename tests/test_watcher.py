"""Unit tests for the watcher's pure logic — no network, no files."""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from watcher import enqueue_candidates, heartbeat_is_stale

NOW = "2026-06-10T18:00:00+00:00"


# ── enqueue_candidates ──────────────────────────────────────────────

def test_enqueue_into_empty_inbox():
    out = enqueue_candidates("", ["candidates/2026-06-10/ABC-1400"], NOW)
    lines = [json.loads(l) for l in out.splitlines()]
    assert lines == [{"folder": "candidates/2026-06-10/ABC-1400", "queued_at": NOW, "status": "pending"}]


def test_enqueue_skips_already_queued():
    existing = json.dumps({"folder": "f1", "queued_at": "x", "status": "pending"}) + "\n"
    out = enqueue_candidates(existing, ["f1", "f2"], NOW)
    folders = [json.loads(l)["folder"] for l in out.splitlines()]
    assert folders == ["f1", "f2"]  # f1 not duplicated


def test_enqueue_preserves_existing_lines_verbatim():
    existing = json.dumps({"folder": "f1", "queued_at": "x", "status": "done"}) + "\n"
    out = enqueue_candidates(existing, ["f2"], NOW)
    assert out.startswith(existing)


def test_enqueue_tolerates_corrupt_lines():
    out = enqueue_candidates("not-json\n", ["f1"], NOW)
    assert "f1" in out and out.startswith("not-json\n")


# ── heartbeat_is_stale ──────────────────────────────────────────────

def _iso(dt):
    return dt.isoformat()

NOW_DT = datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc)


def test_fresh_heartbeat_not_stale():
    assert not heartbeat_is_stale(_iso(NOW_DT - timedelta(seconds=60)), NOW_DT)


def test_old_heartbeat_is_stale():
    assert heartbeat_is_stale(_iso(NOW_DT - timedelta(seconds=600)), NOW_DT)


def test_missing_heartbeat_is_stale():
    assert heartbeat_is_stale(None, NOW_DT)
    assert heartbeat_is_stale("", NOW_DT)


def test_garbage_heartbeat_is_stale():
    assert heartbeat_is_stale("yesterday-ish", NOW_DT)


# ── candidate alert text ────────────────────────────────────────────

from watcher import candidate_alert_text


def test_alert_lists_ticker_move_and_volume():
    text = candidate_alert_text([
        {"ticker": "ELVN", "pct_move": 9.8, "volume_multiple": 7.1},
        {"ticker": "FA", "pct_move": -7.3, "volume_multiple": 3.4},
    ])
    assert text == "ELVN +9.8% vol×7.1\nFA -7.3% vol×3.4"


def test_alert_degrades_to_folder_name_on_unreadable_candidate():
    text = candidate_alert_text([{"folder": "/x/candidates/2026-06-12/TGB-1202"}])
    assert text == "TGB-1202 ?%"


def test_alert_truncates_past_limit():
    cands = [{"ticker": f"T{i}", "pct_move": 5.0, "volume_multiple": 2.0} for i in range(10)]
    text = candidate_alert_text(cands, limit=8)
    assert text.endswith("…and 2 more") and text.count("\n") == 8
