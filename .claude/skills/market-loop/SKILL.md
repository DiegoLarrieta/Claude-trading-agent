---
name: market-loop
description: Run the trading firm as a self-pacing loop for the whole market session - tick every few minutes, drain the watcher's inbox, run committees on what's fresh, guard stops, and wind down at the close. Use when the user says "/market-loop", "run the loop", or wants the firm working the session unattended between confirmations.
---

# Market Loop — the firm's session as a self-pacing tick loop

You are running the same firm as `/trading-day`, but shaped as a **loop of short ticks** instead of one long pass. Each tick does a bounded amount of work, reports in a few lines, and schedules its own wake-up with `ScheduleWakeup` (prompt: `/market-loop`, so the next firing re-enters this skill). Everything substantive — committee mechanics, proposal validation, the fill record, the exit manager — is defined in `.claude/skills/trading-day/SKILL.md` and is NOT redefined here: **when a tick reaches one of those steps, follow /trading-day's procedure verbatim** (especially step 4 — the ONLY path that writes `journal/portfolio.json`).

Get the current time from the hook's CURRENT TIME stamp or `date` — never estimate it.

## First tick (loop startup)

Run this once, when the loop starts (no `.session-state.json` saying `active`, or no morning briefing for today):

1. If the market is closed (outside 09:30–16:00 ET Mon–Fri), say so and stop — do not schedule a wake-up. Offer `/trading-day`'s closed-market options instead.
2. Read `config/limits.yaml`; if `kill_switch: true`, stop and tell the user.
3. `.venv/bin/python scanner/session_state.py set active` — the watchdog now holds you to a fresh heartbeat.
4. /trading-day step 0.2–0.4: today's folders, morning briefing (reporter), radar items.
5. If positions are open, /trading-day step 4.5: launch **exit-manager** for the position review.
6. Confirm the watcher is alive (`journal/.watcher-heartbeat` fresher than 5 min). If it's down, tell the user and apply /trading-day's degraded-mode fallback rules.
7. Fall through into a normal tick.

## Every tick

In order, skipping nothing:

1. **Heartbeat:** `.venv/bin/python scanner/session_state.py touch` — first thing, every tick, even an empty one. This is the promise the watchdog checks.
2. **Stops:** check open positions against their stops (live yfinance prices). A breached stop = simulated exit at the stop price per /trading-day step 5 — record it and tell the user immediately.
3. **Drain:** `.venv/bin/python scanner/inbox_queue.py pending`. Stale candidates are marked automatically; never analyze them.
4. **Triage:** if there are fresh candidates, ONE batch **triage-analyst** spawn for all of them (/trading-day step 2); `finish ... killed` each KILL.
5. **Committees:** for at most `committee_top_k` survivors, in rank order, run /trading-day step 3 (parallel analysts → bear → head trader → validator → bear final). Survivors beyond top-K stay claimable for the next tick.
6. **Confirmation:** CLEARED proposals go to the user via /trading-day step 4 — AskUserQuestion, re-validate on Confirm, record the fill through the validated path. Diego confirms every trade; the loop never assumes an answer.
7. **Report:** a few lines max. An empty tick (no breaches, no fresh candidates) reports exactly ONE line, e.g. `tick 14:05 — quiet: 0 fresh, 2 positions safe, watcher alive`.
8. **Material news on a held name** (a candidate folder for a ticker we hold, or the user flags it): run the exit-manager pass (/trading-day step 4.5) before the next sleep.

## Scheduling the next tick

After the tick's report, call `ScheduleWakeup` with `prompt: "/market-loop"`:

- **Work pending** (fresh candidates waiting, committees mid-flight, a proposal just confirmed): `delaySeconds: 270` — stay in the cache window and come back fast.
- **Quiet market:** `delaySeconds: 600` — accept the cache miss; a 10-minute tick still beats the queue's 45-minute staleness clock.
- **Never sleep past 720** — the session watchdog alerts at a 15-minute-stale heartbeat, and a longer sleep makes the firm cry wolf about itself.
- Within ~15 min of the close, size the delay to land a tick just after 16:00 ET for the wind-down.

Do NOT schedule a wake-up when: the market has closed and the wind-down tick ran; the user said stop/pause; `kill_switch` is true; or the degradation ladder reached rung 3. Not scheduling IS how the loop ends — say so explicitly when you do it.

## Pause / resume

If the user pauses (or you detect a gap — lid close, usage lock): follow the `/pause` skill exactly. Pausing means `session_state.py set paused --note ...` and NO wake-up scheduled. On resume, `session_state.py resume-brief` — its catch-up order (STOPS FIRST, then backlog, then fresh look) is law — then `set active` and re-enter the loop.

## Degradation ladder (token budget)

The loop must degrade loudly, never silently. Step down one rung at a time and TELL the user at each step:

1. **Full loop** — the default above.
2. **Conserve** — when usage warnings appear or the scanner's 80% budget alert fires: committees only for watchlist names and the single top-ranked candidate (K=1); everything else gets triage + a one-line journal note; quiet ticks stretch to 600s.
3. **Notification mode** — budget exhausted or session usage locked: no more committees. Ticks shrink to heartbeat + stop-guard + drain (statuses only, candidates wait); remind the user the watcher's Telegram alerts still cover them. If even ticking is impossible (usage lock), `session_state.py set paused --note "usage lock"` and stop scheduling — the watcher daemon guards stops regardless, and the watchdog/dead-man stay silent for a *paused* session instead of alarming on a dark *active* one.

## Wind-down tick (after the close)

1. Final stop check and inbox drain (statuses only — no new committees after the close).
2. /trading-day step 5: **reporter** evening report; show the P&L line and considered-and-passed list.
3. `.venv/bin/python scanner/inbox_queue.py rotate` and `.venv/bin/python scanner/session_state.py set ended`.
4. Report the day in a few lines and do NOT schedule a wake-up. The loop is over.

## Rules

- All /trading-day rules apply unchanged: no invented market data, `portfolio.json` only through step 4's validated path, `config/limits.yaml` is the law.
- One scanner: the watcher. The loop never runs `scan.py` while the watcher heartbeat is fresh.
- Ticks are terse. The user reads a feed, not essays; save the prose for proposals and the evening report.
- Never trade to justify the loop's existence. A whole session of one-line quiet ticks is a perfectly good day.
