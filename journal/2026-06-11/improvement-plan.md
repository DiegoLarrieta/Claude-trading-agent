# The Firm Upgrade Plan — built tonight (2026-06-11), live tomorrow

Produced by /plan-eng-review with Diego, evening of day 2. Every decision below
was made explicitly during the review (decision IDs in parentheses). Scope:
**comprehensive** — the loop, the agents, the skills, the infrastructure, all
built tonight, all active tomorrow with a degradation parachute (T2-A).

## The goal in one sentence

Turn the firm from a "run /trading-day once" tool into a **market-hours loop**:
the Mac stays awake and scanning, the session ticks all day, candidates flow
from the watcher's queue through the committee, Diego confirms at the Mac, and
deliberate or accidental blindness is always loud and always recovered from.

## Target architecture

```
                         MARKET HOURS (8:30–15:00 CDMX / 9:30–16:00 ET)
┌────────────────────────────────────────────────────────────────────────┐
│ watcher.py — daemon, deterministic, SOLE SCANNER (1A)                  │
│  ├─ scan every 120s ──► candidates/inbox/pending.jsonl (append-only)   │
│  │    └─ pre-triage in scan.py kills mechanical junk for $0 (W4)       │
│  ├─ stop checks every 180s (monitor.py — NEVER pauses)        (2A/#4)  │
│  ├─ heartbeat file every 60s + healthchecks.io dead-man ping  (2A)     │
│  └─ budget alerts: 80% warning, exhaustion alert              (6A)     │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │ file handoff (no shared writes:
                               │  watcher appends pending.jsonl;
                               │  loop appends processed.jsonl)
┌──────────────────────────────▼─────────────────────────────────────────┐
│ Interactive Claude session — /market-loop (3A, driven by /loop)        │
│  first tick:  morning briefing + exit-manager position review          │
│  each tick:   read ledger → new pending? batch-triage → top-K          │
│               committee → Diego confirms on screen → record fill       │
│               → append statuses → write session-heartbeat → sleep      │
│  empty tick:  one quiet line, near-zero tokens                         │
│  /pause:      journal a deliberate blind window; LLM loop only —       │
│               the monitor daemon keeps guarding stops                  │
│  resume:      stops first → queue backlog (stale-killed) → fresh look  │
│  parachute:   usage climbing toward Pro limits → fall back to          │
│               notification-mode instead of going dark (T2-A)           │
│  last tick:   evening report + inbox rotation/archive                  │
└────────────────────────────────────────────────────────────────────────┘
```

## Workstreams

### W1 — Queue protocol: one scanner, statuses, staleness (1A + outside-voice #2/#3/#12)
- The watcher is the **sole scanner**. Delete the self-scan step from
  `/trading-day`; keep a documented manual `scan now` fallback command for
  degraded mode (watcher down), never as an automatic second path.
- Status ledger: the loop never rewrites the watcher's append-only
  `pending.jsonl`; it appends status events to `processed.jsonl`
  (`pending → processing → done | killed | stale`). Two files, no shared
  writes, no locking — the race dies by design. **[CRITICAL requirement]**
- Crash recovery: an entry stuck in `processing` is re-evaluated on the next
  tick, not silently lost.
- **Staleness TTL:** a candidate picked up too long after `queued_at`
  (start: 45 min, tunable) is marked `stale` and journaled, never analyzed —
  a momentum pop from two hours ago is a dead setup (#3).
- Backlog-age alert: oldest pending entry exceeds the TTL while unprocessed →
  notify (yesterday's 2:44pm batch must never rot silently again).
- Daily rotation: the evening tick archives the day's inbox files (#12).

### W2 — Reliability package (2A + #4/#7)
- `caffeinate` wired into `ops/firm` for market hours (Mac stays awake).
- Fix the launchd EX_CONFIG install; add `KeepAlive` so a crashed watcher
  restarts itself (#2 — alerting on death is not a restart story).
- External dead-man: watcher pings healthchecks.io every tick, fire-and-forget
  (a ping failure must never crash the tick). Pings stop for ANY reason —
  lid close, power loss, crash — Diego's phone hears about it.
- **/pause semantics (settled, #4):** /pause blinds ONLY the LLM loop and
  journals the window. The monitor daemon never pauses while the Mac is awake.
  The resume catch-up (stops → backlog → fresh look) exists for true Mac-sleep
  windows, where everything was dark.
- **Session heartbeat (#7):** each loop tick touches
  `journal/.session-heartbeat`; `heartbeat_check.py` watches it during market
  hours — a wedged, compacted-to-death, or usage-locked session becomes loud
  within minutes instead of silently dark.

### W3 — The market loop (3A)
- New skill `/market-loop`, tick-shaped, driven by the harness's `/loop` with
  self-paced wake-ups. `/trading-day`'s committee pipeline (triage → parallel
  analysts → bear → validator → head trader → bear-final → human confirm →
  validated fill path) survives unchanged as the per-candidate engine.
- First tick = morning briefing + exit-manager review; last tick = evening
  report + rotation. Empty-inbox tick = one line, near-zero tokens.
- **Degradation ladder (T2-A):** the loop tracks its own work volume; if usage
  trends toward Pro limits, it announces the fallback and switches to
  notification-mode (watcher keeps scanning + alerting; Diego processes
  candidates in short bursts on demand). An LLM blackout becomes
  impossible-by-design — the same lesson as scanner budget exhaustion (#1).

### W4 — Token economy (born from today's 100k-tokens-zero-trades run)
- **Free pre-triage** in `scan.py`: mechanical kills (illiquid, leveraged ETF,
  blacklist, earnings-day reaction, duplicate-of-today) move from the haiku
  triage prompt into deterministic code. The LLM only sees genuine maybes.
- **Batch triage:** one triage call evaluates all new survivors per tick
  (N verdicts per call), replacing N per-candidate spawns.
- **Committee top-K:** at most 2–3 committees per tick, ranked by
  move × volume × watchlist bonus; the rest wait their turn and may go stale
  honestly. Design-doc target was 3–10 alerts/day — the funnel now matches it.
- Target: a 59-candidate day like today at roughly a quarter of the cost.

### W5 — Analyst quality (4C)
- `config/agents.yaml`: `news_analyst: haiku → sonnet` (precedent: the
  technical analyst's 2026-06-10 promotion). Sentiment stays haiku for now —
  its primary source is deterministic tool output, which the orchestrator can
  re-run cheaply to spot-check.
- Evidence-pasting rules in `news-analyst.md` and `sentiment-analyst.md`:
  every claim sits next to the verbatim quote / raw tool output that supports
  it. An invented fact has no quote and dies on sight.
- Bear duty added: verify memo claims against their pasted evidence, and
  **re-fetch the single most load-bearing source per candidate** (bounded
  cost, real verification — pasted "quotes" alone only prove the memo agrees
  with itself, outside-voice #5).

### W6 — Momentum doctrine (5A, amended by T1)
- Momentum-continuation becomes a recognized setup in the prompts that
  currently speak only dip: `technical-analyst.md` (SHAPE + pop entry
  geometry: is the breakout level holding, is volume confirming, stop below
  the shelf — not below yesterday's range), `triage-analyst.md`
  (catalyst-explained pop ≠ auto-KILL), `head-trader.md` (one line).
  Literacy, not cheerleading — the same skepticism that correctly vetoed
  ELVN and IDCC stays fully armed.
- **Scanner threshold UNCHANGED at 3.0x volume (T1).** `/backtest` runs as
  evidence-gathering with a slippage haircut; threshold changes wait for a
  plateau across sweeps and a second market regime (#6, #11).
- Journal tags each trade with the doctrine that produced it
  (`setup: momentum-pop | dip-to-support | ...`) so attribution stays
  readable with everything live at once (T2-A) and the future momentum book
  (TODOS.md) has clean evidence.
- Fill-quality tracking: the journal records fill price vs proposal reference
  price per trade — the F drill already showed real friction (commission took
  $14.23 to a $14.3753 cost basis); momentum entries are where slippage
  bleeds (#11).

### W7 — Scanner budget alerts (6A)
- Warning at 80% of `max_candidates_per_day`, loud alert at exhaustion, each
  fired once per threshold per day, through the existing `notify()` path
  (macOS + Telegram mirror). Budget state is exposed so `/status` and the
  resume catch-up can report it. Closes lesson #7 for good.

### W8 — Rehearsal + tomorrow's docket
- Tonight, after the build: `/paper-trade` replay against today's completed
  data to exercise the full tick loop end to end before it meets a live
  market (outside-voice #8 — the dry-run exists; use it).
- Tomorrow at the open: **UNIT committee review is due** (watch-level tripwire
  fired at $12.54, breakout held). SpaceX IPO pricing context matters for
  GOOGL (~5–6% stake).

## Tests (written alongside the code, not after)

All new deterministic paths get pytest coverage in the existing `tests/`
convention (pure logic separated from I/O shell):

1. Ledger status transitions happy path (pending→processing→done/killed/stale)
2. Malformed JSONL line skipped, never crashes the tick
3. Crash mid-processing → entry recovered on next tick
4. **Watcher-append + loop-append never touch the same file** (the two-file
   design holds under interleaving) — CRITICAL
5. Staleness TTL: old candidate → `stale`, journaled, not analyzed
6. Daily rotation archives and resets cleanly
7. /pause writes state + timestamp; monitor untouched
8. Resume computes the blind window; missing pause file (crash/sleep) →
   blind-since-last-heartbeat
9. Budget alerts fire at 80% and 100%, once per threshold per day
10. Dead-man ping failure is swallowed (fire-and-forget)
11. Pre-triage mechanical kills match the rules (each rule one case)

LLM-side changes (prompts, loop skill) are forward-tested in tomorrow's live
session per the firm's no-backtest rule; bear-final verdicts and the evening
report are the graders.

## What already exists (reused, not rebuilt)

- `watcher.py` — scan loop, inbox queue, stop checks, heartbeat (becomes sole scanner)
- `monitor.py` — deterministic stop enforcement + raise-only escalation (untouched, never pauses)
- `heartbeat_check.py` — watchdog (gains the session-heartbeat to watch)
- `telegram_bot.py`, `notify()` — alert paths (reused by W6/W7 alerts)
- `validate_proposal.py` — arithmetic law enforcement (unchanged, still gates every proposal)
- `/trading-day`'s committee pipeline — survives as the per-candidate engine inside the loop
- `/paper-trade`, `/start-trade`, `/backtest` — unchanged; `/start-trade` gains caffeinate + new checks
- 11 existing test files — extended, conventions followed
- Harness `/loop` — drives the tick; no custom loop infra built

## NOT in scope (explicitly deferred, see TODOS.md)

- **Telegram phone-confirmation path** — Diego is at the Mac; deferred until the loop is stable (TODOS.md #1)
- **Momentum book with own sizing** (5C) — graduates only on live doctrine evidence + slippage-haircut backtests across a second regime (TODOS.md #2)
- **Scanner volume threshold change 3.0x→2.5x** — rejected for now (T1)
- **IBKR live trading** — Stage 4, gated on the simulated track record (unchanged)
- **Reddit OAuth sentiment source** — already tracked, pending API approval

## Failure modes (each addressed)

| Failure | Detection | Handling |
|---|---|---|
| Watcher/loop write race on the queue | impossible-by-design (two files) | test #4 guards the invariant |
| Candidate rots in queue | backlog-age alert | staleness TTL kills it honestly |
| Mac sleeps with positions open | healthchecks.io (off-Mac) | resume catch-up: stops first |
| Session wedges / compacts badly / hits limits | session-heartbeat + heartbeat_check | degradation ladder to notification-mode |
| Watcher crashes | dead-man + heartbeat | launchd KeepAlive restarts it |
| Scanner budget exhausted | 80% + 100% alerts | Diego can raise the cap mid-day |
| Fabricated memo claim | evidence-pasting + bear re-fetch | claim without quote = objection |

No silent critical gaps remain: every identified failure has detection AND handling AND is user-visible.

## Implementation order (tonight)

| Lane | Work | Touches | Depends on |
|---|---|---|---|
| A | W1 queue protocol → W4 pre-triage/batch → W7 alerts | `scanner/`, `tests/` | — |
| B | W2 reliability (caffeinate, launchd, dead-man, /pause state) | `ops/`, `scanner/watcher.py`, `tests/` | — (coordinate watcher.py edits with lane A) |
| C | W5 + W6 prompt doctrine | `.claude/agents/`, `config/agents.yaml` | — |
| D | W3 /market-loop skill | `.claude/skills/` | lane A's ledger format |
| E | W8 rehearsal via /paper-trade | — | A–D done |

Lanes A, B, C can run in parallel (one watcher.py conflict flagged between
A and B — coordinate or sequence those two edits). D needs A's ledger format.
E is the gate before bed: the loop must survive a replay of today before it
meets tomorrow.

## Tomorrow's success criteria

- The loop runs from open to close; empty ticks cost near-nothing; the
  session-heartbeat never goes stale unnoticed.
- A 59-candidate day costs a fraction of today's 100k tokens.
- UNIT gets its committee review at the open.
- Any momentum pop that fires reaches a committee that speaks momentum —
  and still has to survive the bear.
- /pause + resume used at least once deliberately, catch-up verified.
- Evening report can attribute every decision to plumbing vs doctrine.
