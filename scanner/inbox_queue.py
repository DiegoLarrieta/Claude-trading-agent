#!/usr/bin/env python
"""Candidate queue protocol — two files, one writer each, append-only.

The watcher (the firm's SOLE scanner) appends candidate entries to
candidates/inbox/pending.jsonl and never touches anything else. The
interactive session never rewrites that file; it appends status events to
candidates/inbox/processed.jsonl instead:

    {"folder": ..., "status": "processing|done|killed|rejected|stale",
     "at": ISO-UTC, "note": "..."}

The LAST status line for a folder wins. Two files, a single writer for
each — no locking, no read-modify-write race, crash recovery for free
(a folder stuck in "processing" past the timeout is offered again).

CLI used by the trading-day / market-loop skills:
  inbox_queue.py pending                 # mark stale entries, print fresh ones ranked
  inbox_queue.py claim FOLDER            # status=processing
  inbox_queue.py finish FOLDER STATUS [--note ...]
  inbox_queue.py rotate                  # archive the inbox files (evening)
No LLM in this file. (Named inbox_queue, not queue — scanner/ sits on
sys.path and queue.py would shadow the stdlib module urllib3 imports.)
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX_DIR = ROOT / "candidates" / "inbox"
PENDING = INBOX_DIR / "pending.jsonl"
PROCESSED = INBOX_DIR / "processed.jsonl"
ARCHIVE = INBOX_DIR / "archive"

TERMINAL = {"done", "killed", "rejected", "stale"}
VALID_FINISH = {"done", "killed", "rejected"}


# ── pure logic (unit-tested, no I/O) ────────────────────────────────


def parse_jsonl(text: str) -> list[dict]:
    """Parse JSONL leniently — a malformed line is skipped, never fatal."""
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def latest_statuses(status_records: list[dict]) -> dict[str, dict]:
    """Last status line per folder wins (the file is append-only)."""
    latest = {}
    for rec in status_records:
        folder = rec.get("folder")
        if folder and rec.get("status"):
            latest[folder] = rec
    return latest


def _age_minutes(iso: str | None, now: datetime) -> float | None:
    if not iso:
        return None
    try:
        return (now - datetime.fromisoformat(iso)).total_seconds() / 60
    except ValueError:
        return None


def split_pending(entries: list[dict], statuses: dict[str, dict], now: datetime,
                  stale_after_min: float = 45, processing_timeout_min: float = 30,
                  ) -> tuple[list[dict], list[dict]]:
    """Split queue entries into (fresh, stale).

    fresh — never processed (or stuck in 'processing' past the timeout:
            crash recovery) and younger than the staleness TTL.
    stale — unprocessed but older than the TTL; a momentum setup from an
            hour ago is dead and gets journaled, never analyzed.
    Terminal statuses and live 'processing' claims are skipped entirely.
    An unparseable queued_at is treated as stale (never analyze blind).
    """
    fresh, stale = [], []
    for entry in entries:
        folder = entry.get("folder")
        if not folder:
            continue
        st = statuses.get(folder)
        if st:
            if st["status"] in TERMINAL:
                continue
            if st["status"] == "processing":
                claim_age = _age_minutes(st.get("at"), now)
                if claim_age is not None and claim_age <= processing_timeout_min:
                    continue  # someone is on it
        queued_age = _age_minutes(entry.get("queued_at"), now)
        if queued_age is None or queued_age > stale_after_min:
            stale.append(entry)
        else:
            fresh.append(entry)
    return fresh, stale


def rank(candidates: list[dict]) -> list[dict]:
    """Order candidates for the committee: biggest confirmed move first.

    score = |pct_move| x volume_multiple (floored at 1), x1.5 if watchlist.
    """
    def score(c):
        s = abs(c.get("pct_move") or 0) * max(c.get("volume_multiple") or 0, 1)
        return s * 1.5 if c.get("watchlist") else s
    return sorted(candidates, key=score, reverse=True)


def oldest_unprocessed_age_minutes(entries: list[dict], statuses: dict[str, dict],
                                   now: datetime) -> float | None:
    """Age of the oldest entry nobody has touched yet — the backlog alarm.

    'Touched' means any status at all, including a live processing claim;
    the alarm is about candidates rotting unseen, not slow committees.
    """
    ages = [
        _age_minutes(e.get("queued_at"), now)
        for e in entries
        if e.get("folder") and e["folder"] not in statuses
    ]
    ages = [a for a in ages if a is not None]
    return max(ages) if ages else None


def status_line(folder: str, status: str, now_iso: str, note: str | None = None) -> str:
    rec = {"folder": folder, "status": status, "at": now_iso}
    if note:
        rec["note"] = note
    return json.dumps(rec) + "\n"


# ── I/O shell ───────────────────────────────────────────────────────


def _read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def append_status(folder: str, status: str, note: str | None = None) -> None:
    """The ONLY write the session side ever makes: append to processed.jsonl."""
    PROCESSED.parent.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()
    with PROCESSED.open("a") as f:
        f.write(status_line(folder, status, now_iso, note))


def _queue_cfg() -> dict:
    import yaml
    cfg = yaml.safe_load((ROOT / "config" / "scanner.yaml").read_text())
    return cfg.get("queue") or {}


def load_candidate(folder: str) -> dict:
    path = ROOT / folder / "candidate.json"
    if not path.is_absolute() and not path.exists():
        path = Path(folder) / "candidate.json"
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def cmd_pending() -> None:
    """Mark stale entries, then print fresh candidates in committee order."""
    cfg = _queue_cfg()
    now = datetime.now(timezone.utc)
    entries = parse_jsonl(_read(PENDING))
    statuses = latest_statuses(parse_jsonl(_read(PROCESSED)))
    fresh, stale = split_pending(
        entries, statuses, now,
        stale_after_min=cfg.get("stale_after_minutes", 45),
        processing_timeout_min=cfg.get("processing_timeout_minutes", 30))
    for entry in stale:
        age = _age_minutes(entry.get("queued_at"), now)
        note = f"queued {age:.0f} min ago — setup expired unseen" if age else "unparseable queued_at"
        append_status(entry["folder"], "stale", note)
        print(f"STALE {entry['folder']} ({note})")
    enriched = []
    for entry in fresh:
        cand = load_candidate(entry["folder"])
        enriched.append({**cand, "folder": entry["folder"], "queued_at": entry.get("queued_at")})
    top_k = cfg.get("committee_top_k", 3)
    for i, cand in enumerate(rank(enriched), start=1):
        flag = "TOP-K" if i <= top_k else "WAIT"
        print(f"{flag} #{i} {cand['folder']} "
              f"{cand.get('ticker', '?')} {cand.get('pct_move', 0):+.1f}% "
              f"vol×{cand.get('volume_multiple', 0)}"
              f"{' [watchlist]' if cand.get('watchlist') else ''}")
    print(f"SUMMARY fresh={len(fresh)} stale={len(stale)} top_k={top_k}")


def cmd_rotate() -> None:
    """Archive the inbox files (evening). The watcher must not be running."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    for path in (PENDING, PROCESSED):
        if path.exists() and path.read_text().strip():
            dest = ARCHIVE / f"{today}-{path.name}"
            dest.write_text(path.read_text())
            path.write_text("")
            print(f"archived {path.name} -> {dest.relative_to(ROOT)}")
        else:
            print(f"{path.name}: empty, nothing to archive")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pending")
    p_claim = sub.add_parser("claim")
    p_claim.add_argument("folder")
    p_fin = sub.add_parser("finish")
    p_fin.add_argument("folder")
    p_fin.add_argument("status", choices=sorted(VALID_FINISH))
    p_fin.add_argument("--note", default=None)
    sub.add_parser("rotate")
    args = ap.parse_args()
    if args.cmd == "pending":
        cmd_pending()
    elif args.cmd == "claim":
        append_status(args.folder, "processing")
        print(f"claimed {args.folder}")
    elif args.cmd == "finish":
        append_status(args.folder, args.status, args.note)
        print(f"{args.status} {args.folder}")
    elif args.cmd == "rotate":
        cmd_rotate()


if __name__ == "__main__":
    main()
