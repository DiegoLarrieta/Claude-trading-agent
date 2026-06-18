# Improvement Plan — living backlog

*Written 2026-06-17 after the week's first real FOMC hold. Prioritized by impact. Items marked 🔒 are human-only (touch `config/limits.yaml` or remove a safety lock) — I can draft, only Diego decides. Everything else I can implement on request.*

---

## A. Trading edge — does the firm actually make money?

1. **Resolve the VST dip-buy experiment, then rule on it.** VST is the firm's one open thesis and an explicit test of whether a *fundamentals-filtered* dip-buy beats the negative-expectancy *undifferentiated* dip-buy backtest (lessons #4/#8). It's ~flat after FOMC — **one inconclusive data point.** Action: track it to its exit (target/stop/thesis-break), then have the reporter score it. Don't take a second filtered dip-buy as "proven" until this resolves. *(Owner: me, ongoing.)*

2. **Stop feeding extended momentum pops into the committee.** Four names this week — AMD, AMKR, LION (+MRVL passed pre-committee) — all died on the same axis: already-extended + broken R:R + event gap. We burned real committee tokens to reach a "no" the chart already implied. **Fix options (pick one):**
   - Scanner/triage filter: down-rank or auto-flag candidates already >X% above their 20-day MA or within Y% of the 52-week high, so triage kills the chase cheaply. 🔒 if it touches `config/scanner.yaml` thresholds.
   - A cheap pre-triage "extension check" the loop runs before spawning analysts.
   *Impact: saves tokens AND enforces the lesson mechanically instead of relying on the bear every time.*

3. **Bias to fewer, larger bets.** The $1/trade IB fee (~$2 round-trip) is ~2% of a $100 exploratory nibble — a real hurdle. The head trader should weigh fee drag in sizing and prefer one conviction-sized bet over several nibbles. *(Owner: me — fold into the head-trader prompt / sizing notes.)*

---

## B. Execution gaps exposed this week

4. **The broker can't SELL.** `scanner/broker.py` is buy-only — we could not close F or VST through the firm; both required Diego to act by hand, risking journal/account desync. Action: add a validated **sell/close path** to `broker.py` (same paper-port lock, same read-only refusal of live ports). This is the single biggest execution gap. 🔒 (new order-capable code path — Diego reviews.)

5. **Fractional orders fail via the IBKR API** (error 10243 — VST 0.63 sh rejected, forced to 1 whole share). Action: make `validate_proposal.py`/sizing **round to whole shares for paper-account orders**, or detect-and-warn, so a proposed size is actually executable. *(Owner: me.)*

6. **Clarify the accounting model.** The journal now blends three things: simulated fills, real-mirrored fills (VST, with the $1 fee), and discretionary no-stop holds (NVDA). Action: document/normalize how `cash_usd`, exposure caps, and P&L treat each bucket so the track record stays honest. *(Owner: me — draft for Diego's sign-off.)*

---

## C. Reliability — the daemons keep scaring us

7. **Make the watcher log tell the truth.** stdout is block-buffered under launchd, so the log shows a stale `"session over"` line while the watcher is actually alive — this is *why* "are the daemons up?" came up ~6 times this week. Fix: add `PYTHONUNBUFFERED=1` (or `python -u`) to the watcher/telegram launchd plists. **One-line, high-annoyance-payoff.** *(Owner: me — offered, awaiting OK.)*

8. **Survive the Homebrew-python rebuild.** Daemons died with exit 78 after a `python@3.14` rebuild invalidated the log files' `com.apple.macl` stamp. Fix: a boot self-check (`ops/firm`) that detects the stale-macl/78 condition and auto-clears the log files, so it self-heals instead of needing a manual diagnosis. *(Owner: me. See memory `daemons-macl-78-gotcha`.)*

9. **End sessions to stop SESSION DARK spam.** Root-caused: leaving the session `active` overnight → watchdog alerts every cycle. Decision already made (keep the 15-min limit, be disciplined about `set ended`). Reinforce: the wind-down must always run `set ended`, even on abrupt/token-out stops. *(Owner: me — discipline. See memory `end-session-discipline`.)*

---

## D. Housekeeping (done / ongoing)
- ✅ Repo hygiene — stopped tracking runtime logs/state, gitignored them (PR #26 merged).
- ✅ STATE-OF-THE-FIRM.md map committed.
- ⏳ Keep `lessons.md` honest — only promote a pattern to a lesson when it would have changed a decision (the momentum-veto pattern is *observed* but already covered by #4/#8; not promoted).

---

## Suggested order for the next working session
1. **#7** (unbuffered logs) — trivial, kills the recurring "are daemons up?" confusion.
2. **#5** (whole-share sizing) — small, prevents the next rejected order.
3. **#2** (extension filter) — saves tokens every session.
4. **#4** (broker sell path) — the big one; needs design + Diego's review.
