"""Unit tests for the queue protocol's pure logic — no network, no files."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from inbox_queue import (
    latest_statuses,
    oldest_unprocessed_age_minutes,
    parse_jsonl,
    rank,
    split_pending,
    status_line,
)
from watcher import enqueue_candidates

NOW = datetime(2026, 6, 12, 15, 0, tzinfo=timezone.utc)


def _iso(minutes_ago: float) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).isoformat()


def _entry(folder: str, minutes_ago: float) -> dict:
    return {"folder": folder, "queued_at": _iso(minutes_ago), "status": "pending"}


def _status(folder: str, status: str, minutes_ago: float) -> dict:
    return {"folder": folder, "status": status, "at": _iso(minutes_ago)}


# ── parse_jsonl ─────────────────────────────────────────────────────

def test_parse_skips_malformed_lines_without_crashing():
    text = json.dumps(_entry("f1", 5)) + "\nnot-json\n[1,2]\n" + json.dumps(_entry("f2", 5)) + "\n"
    folders = [r["folder"] for r in parse_jsonl(text)]
    assert folders == ["f1", "f2"]


def test_parse_empty_text():
    assert parse_jsonl("") == []


# ── latest_statuses ─────────────────────────────────────────────────

def test_last_status_line_wins():
    records = [_status("f1", "processing", 20), _status("f1", "done", 5)]
    assert latest_statuses(records)["f1"]["status"] == "done"


# ── split_pending: the lifecycle ────────────────────────────────────

def test_happy_path_pending_to_done():
    entries = [_entry("f1", 5)]
    fresh, stale = split_pending(entries, {}, NOW)
    assert [e["folder"] for e in fresh] == ["f1"] and stale == []
    # claimed -> not offered again while the claim is live
    fresh, _ = split_pending(entries, latest_statuses([_status("f1", "processing", 1)]), NOW)
    assert fresh == []
    # finished -> never offered again
    for terminal in ("done", "killed", "rejected", "stale"):
        fresh, stale = split_pending(entries, latest_statuses([_status("f1", terminal, 1)]), NOW)
        assert fresh == [] and stale == []


def test_crash_recovery_reoffers_expired_processing_claim():
    entries = [_entry("f1", 10)]
    statuses = latest_statuses([_status("f1", "processing", 31)])
    fresh, stale = split_pending(entries, statuses, NOW, processing_timeout_min=30)
    assert [e["folder"] for e in fresh] == ["f1"] and stale == []


def test_stale_ttl_kills_old_unprocessed_candidate():
    fresh, stale = split_pending([_entry("old", 46), _entry("new", 10)], {}, NOW,
                                 stale_after_min=45)
    assert [e["folder"] for e in fresh] == ["new"]
    assert [e["folder"] for e in stale] == ["old"]


def test_unparseable_queued_at_is_stale_never_analyzed():
    entries = [{"folder": "f1", "queued_at": "yesterday-ish", "status": "pending"}]
    fresh, stale = split_pending(entries, {}, NOW)
    assert fresh == [] and [e["folder"] for e in stale] == ["f1"]


def test_expired_claim_on_expired_candidate_goes_stale_not_fresh():
    entries = [_entry("f1", 90)]
    statuses = latest_statuses([_status("f1", "processing", 60)])
    fresh, stale = split_pending(entries, statuses, NOW)
    assert fresh == [] and [e["folder"] for e in stale] == ["f1"]


# ── the two-file invariant (CRITICAL) ───────────────────────────────

def test_interleaved_writes_never_corrupt_either_file():
    """Watcher appends pending.jsonl; session appends processed.jsonl.
    Simulate interleaving and assert both stay parseable and consistent."""
    pending_text, processed_text = "", ""
    pending_text = enqueue_candidates(pending_text, ["f1"], _iso(10))
    processed_text += status_line("f1", "processing", _iso(9))
    pending_text = enqueue_candidates(pending_text, ["f2", "f3"], _iso(8))
    processed_text += status_line("f1", "done", _iso(7), note="CLEARED")
    processed_text += status_line("f2", "killed", _iso(6))
    pending_text = enqueue_candidates(pending_text, ["f1", "f4"], _iso(5))  # f1 deduped

    entries = parse_jsonl(pending_text)
    assert [e["folder"] for e in entries] == ["f1", "f2", "f3", "f4"]
    statuses = latest_statuses(parse_jsonl(processed_text))
    fresh, stale = split_pending(entries, statuses, NOW)
    assert [e["folder"] for e in fresh] == ["f3", "f4"] and stale == []


def test_status_for_unknown_folder_is_harmless():
    # manual-fallback candidates get statuses before (or without) ever being enqueued
    statuses = latest_statuses([_status("manual-folder", "done", 5)])
    fresh, stale = split_pending([_entry("f1", 5)], statuses, NOW)
    assert [e["folder"] for e in fresh] == ["f1"] and stale == []


# ── rank ────────────────────────────────────────────────────────────

def test_rank_orders_by_move_times_volume_with_watchlist_bonus():
    cands = [
        {"folder": "a", "pct_move": 4.0, "volume_multiple": 2.0},   # 8
        {"folder": "b", "pct_move": -6.0, "volume_multiple": 3.0},  # 18
        {"folder": "c", "pct_move": 5.0, "volume_multiple": 2.5, "watchlist": True},  # 18.75
        {"folder": "d", "pct_move": 9.0, "volume_multiple": 0},     # vol floored at 1 -> 9
    ]
    assert [c["folder"] for c in rank(cands)] == ["c", "b", "d", "a"]


def test_rank_tolerates_missing_fields():
    assert [c["folder"] for c in rank([{"folder": "a"}, {"folder": "b", "pct_move": 1}])] == ["b", "a"]


# ── backlog alarm ───────────────────────────────────────────────────

def test_oldest_unprocessed_ignores_touched_entries():
    entries = [_entry("f1", 120), _entry("f2", 50), _entry("f3", 10)]
    statuses = latest_statuses([_status("f1", "processing", 110)])  # touched: not backlog
    age = oldest_unprocessed_age_minutes(entries, statuses, NOW)
    assert age is not None and 49 < age < 51


def test_oldest_unprocessed_none_when_all_touched():
    entries = [_entry("f1", 120)]
    statuses = latest_statuses([_status("f1", "done", 60)])
    assert oldest_unprocessed_age_minutes(entries, statuses, NOW) is None
    assert oldest_unprocessed_age_minutes([], {}, NOW) is None
