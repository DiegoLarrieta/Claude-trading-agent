---
name: pause
description: Pause the firm's LLM side deliberately (closing the laptop, stepping away) and catch up safely on resume. Use when the user says "/pause", "pause", "I need to close my laptop", "stepping away", or — for the other half — "resume", "I'm back", "reopen".
---

# Pause & Resume — deliberate blindness, honest catch-up

The firm has two halves. The **watcher daemon** (stops, scanning, alerts) is deterministic and NEVER pauses while the Mac is awake — pausing stop protection is not a thing this skill can do. What pauses is the **LLM side**: committees, proposals, this session's attention.

## On "/pause" or "stepping away"

1. Record it: `.venv/bin/python scanner/session_state.py set paused --note "<the user's reason, short>"`
2. Tell the user exactly what changes, in three lines:
   - **Still guarded (Mac awake):** stops, watch levels, scanning, budget/backlog alerts — the watcher does all of that without you.
   - **Going dark:** new candidates queue up but nobody analyzes them; anything older than the staleness TTL when you return is dead (marked stale, journaled, never analyzed late).
   - **If the lid closes:** the Mac sleeps and EVERYTHING stops, including stop protection. The external dead-man switch (healthchecks.io) is what notices the silence — if positions are open, say so explicitly before they go.
3. If `journal/portfolio.json` has open positions and the user is about to sleep the Mac, list each position with its stop so they leave with eyes open. This is information, not a veto — it's their laptop.

The paused state silences the SESSION DARK watchdog alert (`heartbeat_check.py` only alarms on a session that claims to be ACTIVE and goes quiet). Pausing keeps the firm honest instead of looking wedged.

## On "resume" / "I'm back"

Run the deterministic brief first — never reconstruct the blind window from memory:

```bash
.venv/bin/python scanner/session_state.py resume-brief
```

It prints how long the firm was blind and the catch-up order, which is law:

1. **Stops first.** Read `journal/portfolio.json`, pull live prices via yfinance, verify every position against its stop. Confirm `journal/.watcher-heartbeat` is fresh — if the Mac slept, the watcher died with it and must be restarted (`ops/firm up`) BEFORE anything else. If a stop was breached during the blind window, deal with it now (the monitor's simulated-exit path), not after triage.
2. **Backlog.** `.venv/bin/python scanner/inbox_queue.py pending` — expired candidates are auto-marked stale; fresh survivors come out ranked. Tell the user what died unseen and what's still alive.
3. **Fresh look.** Mark presence again — `.venv/bin/python scanner/session_state.py set active` — and continue the normal day (top-K committees on survivors, etc.).

Report the whole catch-up to the user in a few lines: blind window, stops status, candidates stale/alive. The blind window is journal material for the evening report.

## Rules

- Never skip or reorder the catch-up. Stops outrank opportunities, always.
- A pause is a deliberate act and gets journaled; an unplanned gap (crash, lid, sleep) shows up as a stale session heartbeat instead — `resume-brief` handles both honestly.
- This skill never touches `config/limits.yaml`, never places orders, never writes `portfolio.json` outside the validated paths.
