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

## 1. Scan (deterministic, no LLM judgment)

Run a market scan with Python/yfinance via Bash against the thresholds in `config/scanner.yaml`:
- Day's top % gainers and losers (use yfinance screeners or a liquid-universe list)
- Volume vs 20-day average for the movers
- Filter by universe rules (market cap, dollar volume, exchanges)

For each ticker that fires a trigger and is not in cooldown (no folder for it today within `cooldown_minutes`), create `candidates/YYYY-MM-DD/TICKER-HHMM/candidate.json`:

```json
{"ticker": "X", "trigger": "pct_move|volume|52w|gap", "pct_move": -6.2,
 "volume_multiple": 4.1, "price": 123.45, "prev_close": 131.6,
 "detected_at": "ISO timestamp", "scanner_notes": "..."}
```

Tell the user how many candidates fired. If zero, say so and skip to step 5 at day's end — a quiet day is a valid day.

## 2. Triage

For each new candidate folder, launch the **triage-analyst** subagent with the folder path. Collect verdicts. Report to the user: "N candidates → M passed triage."

## 3. Committee (per surviving candidate)

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

1. **Present the proposal to the user via AskUserQuestion** — ticker, side, shares, limit, stop, two-line thesis, AND the bear's strongest surviving concern. Options: Confirm / Reject.
2. On **Confirm**: re-run `scanner/validate_proposal.py` (same command as step 3.4 — prices may have drifted since the proposal was written; it recomputes every limit from `journal/portfolio.json`, never trusting memos). Only if VALID, append the simulated fill to `journal/portfolio.json`:

```json
{"ticker": "X", "side": "buy", "shares": N, "fill_price": <limit>,
 "stop": S, "opened_at": "ISO", "thesis": "...",
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

## Rules

- You never invent market data — every number comes from yfinance pulls or memo files.
- You never write to `portfolio.json` except through step 4's validated path.
- Stay quiet between steps; report at the numbered checkpoints in one or two lines each.
- If the market is closed, say so and offer: run anyway on today's completed data (a "paper replay" of today only — never older dates), or just do the evening report.
