---
name: trading-day
description: Run a full (simulated) trading day - scan the live market for opportunities, run candidates through the analyst committee with bear veto, record simulated fills, and produce the evening report. Use when the user says "run a trading day", "/trading-day", "scan the market", or wants the firm to work a session.
---

# Trading Day — the firm's standard operating procedure

You are orchestrating the trading firm defined in `.claude/agents/`. Today's date and live market data are real; fills are SIMULATED (check `config/limits.yaml: mode`). You sequence the pipeline deterministically — the judgment lives in the subagents, not in you.

## 0. Setup

1. Read `config/limits.yaml` (the law), `config/scanner.yaml` (thresholds), `journal/portfolio.json` (state). If `kill_switch: true`, stop and tell the user.
2. Create today's folders if missing: `candidates/YYYY-MM-DD/`, `journal/YYYY-MM-DD/`.
3. If no morning briefing exists for today, launch the **reporter** subagent to write it, and show the user a 3-line summary.
4. If the briefing's **Opportunities radar** has `→ queue for committee` items, present them to the user (one line each). For each one the user wants pursued, create a candidate folder by hand — `candidates/YYYY-MM-DD/TICKER-HHMM/candidate.json` with real yfinance numbers, `"trigger": "radar"`, and the radar's one-line reason in `scanner_notes` — then send it through triage like any scanner candidate. The radar nominates; the committee still decides. Radar candidates must carry the same metadata the scanner stamps — compute it with the scanner's own helpers, never by hand:

   ```bash
   .venv/bin/python -c "
   import sys, yaml; sys.path.insert(0, 'scanner')
   from scan import fetch_days_to_earnings, theme_of, UNIVERSE
   t = 'TICKER'
   print({'days_to_earnings': fetch_days_to_earnings(t),
          'theme': theme_of(t, UNIVERSE), 'watchlist': bool(theme_of(t, UNIVERSE))})"
   ```

## 1. Drain the inbox (the watcher is the SOLE scanner)

You never scan the market yourself — the watcher daemon (`scanner/watcher.py`) is the firm's only scanner. It appends candidates to `candidates/inbox/pending.jsonl`; you consume them through the queue protocol (`scanner/inbox_queue.py`), whose status ledger (`processed.jsonl`) is YOUR file — append-only, and the only inbox file you ever write:

```bash
.venv/bin/python scanner/inbox_queue.py pending
```

This marks expired candidates `stale` (a momentum setup from 45+ minutes ago is dead — journal them, never analyze them) and prints the fresh ones ranked for the committee, the top-K flagged. Before working a candidate, claim it; when its pipeline ends, record the outcome:

```bash
.venv/bin/python scanner/inbox_queue.py claim <folder>
.venv/bin/python scanner/inbox_queue.py finish <folder> done|killed|rejected --note "<one line>"
```

(`killed` = triage kill or bear veto/PASS; `done` = reached a human decision; `rejected` = Diego said no.)

Tell the user how many candidates are fresh, stale, and waiting. If zero, say so — a quiet day is a valid day. First check the watcher is alive (`journal/.watcher-heartbeat` fresher than 5 min); if it's down, tell the user, then as a degraded-mode fallback you may run one scan by hand — `.venv/bin/python scanner/scan.py` — and send the folders it prints straight to triage, recording their statuses in the ledger as usual (the ledger dedupes them if the watcher later re-enqueues). Never run scan.py while the watcher is alive — one scanner, one writer.

## 2. Triage (ONE batch call)

Launch a SINGLE **triage-analyst** subagent with ALL fresh candidate folder paths in one prompt — never one spawn per candidate. Collect verdicts; `finish ... killed` each KILL. Report to the user: "N candidates → M passed triage."

## 3. Committee (per surviving candidate, top-K at a time)

Convene committees for at most `committee_top_k` (config/scanner.yaml, currently 3) triage survivors at a time, in the rank order step 1 printed. The rest wait — they stay claimable on the next drain and may go stale honestly; tell the user who's waiting. For each candidate:

1. Launch **news-analyst**, **technical-analyst**, and **sentiment-analyst** subagents IN PARALLEL (single message, three Agent calls), each with the candidate folder path.
2. When all three memos exist, launch **risk-manager-bear** (pass 1) on the folder.
3. Launch **head-trader** on the folder.
4. If `decision.md` says PROPOSE, validate the proposal deterministically BEFORE the bear's final pass:

   ```bash
   .venv/bin/python scanner/validate_proposal.py --ticker X --shares N --limit L --stop S [--horizon swing]
   ```

   (values from `decision.md`; the script fetches the live price itself). If it prints VIOLATION lines, append them to `decision.md` under `## VALIDATOR REJECTED`, relaunch **head-trader** once to fix or withdraw; if the revised proposal still fails, the candidate becomes a PASS — arithmetic violations are not negotiable.
5. If the proposal is VALID, launch **risk-manager-bear** again (pass 2) for `bear-final.md`.

If any analyst fails or times out, retry once; if it still fails, write `<role>.md` with `DATA UNAVAILABLE — analyst failed` and let the bear treat the gap as an objection. Never silently skip a memo.

## 4. Proposal → human confirmation → simulated fill

For each candidate with `bear-final.md: VERDICT: CLEARED`:

1. **Present the proposal to the user via AskUserQuestion** — ticker, side, shares, limit, stop, horizon (with its one-line reason), two-line thesis, AND the bear's strongest surviving concern. Options: Confirm / Reject.
2. On **Confirm**: re-run `scanner/validate_proposal.py` (same command as step 3.4 — prices may have drifted since the proposal was written; it recomputes every limit from `journal/portfolio.json`, never trusting memos). Only if VALID, execute per `limits.yaml: mode`:
   - **mode: simulation** — record the simulated fill directly (below).
   - **mode: paper** — place the real paper order first: `.venv/bin/python scanner/broker.py order --ticker X --shares N --limit L --stop S --horizon H`. If it reports `Filled`, record the fill below using the actual `avg_fill_price` and add `"broker": "ibkr-paper"` to the record. If unfilled after the wait, tell the user (order works at IBKR until the close; check later with `broker.py orders`); record the position only once filled. If the broker errors, report it verbatim — never fall back to a silent simulated fill.

   Then append the fill to `journal/portfolio.json`:

```json
{"ticker": "X", "side": "buy", "shares": N, "fill_price": <limit>,
 "stop": S, "horizon": "day|swing|core", "opened_at": "ISO", "thesis": "...",
 "candidate_folder": "candidates/.../", "simulated": true}
```

3. On **Reject**: journal it with the user's reason; apply ticker cooldown.
4. VETOED or PASS candidates need no user interaction — they're journal material.

## 4.5 Position review (the exit manager's pass)

Once per session — at session start if positions are open, or after material news breaks on a held name — launch the **exit-manager** subagent. It writes `journal/YYYY-MM-DD/position-review.md` with HOLD / TIGHTEN / CLOSE recommendations per position.

- TIGHTEN: apply by raising the stop in `journal/portfolio.json` (validate: new stop > old stop — the law forbids widening), and tell the user.
- CLOSE: present to the user via AskUserQuestion (recommendation + reason + current P&L). On Confirm, record the simulated exit at the current price with `exit_reason: "discretionary_close"`; on Reject, journal the disagreement — it's scoreboard material.
- HOLD: no action; the review memo is journal material.

## 5. Positions check & evening report

- During the session, also check open positions against their stops (current price via yfinance). A breached stop = simulated exit at the stop price; record the close in `portfolio.json` and inform the user.
- At day's end (or when the user says "wrap up"), launch the **reporter** subagent for the evening report, then show the user the P&L line and the considered-and-passed list inline.
- After the evening report, archive the day's inbox (the watcher has self-terminated by then): `.venv/bin/python scanner/inbox_queue.py rotate`.

## Rules

- You never invent market data — every number comes from yfinance pulls or memo files.
- You never write to `portfolio.json` except through step 4's validated path.
- Stay quiet between steps; report at the numbered checkpoints in one or two lines each.
- If the market is closed, say so and offer: run anyway on today's completed data (a "paper replay" of today only — never older dates), or just do the evening report.
