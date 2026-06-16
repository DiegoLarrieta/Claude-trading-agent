# State of the Firm — your one-page map

*Written 2026-06-13 (weekend, market closed) to put the whole project back on one screen. Plain language. Nothing here is built or changed — this is just the map.*

**Your goal:** a system you eventually trust with real money. The definition of "trustworthy" is already written down in `config/graduation.md` — that file is your finish line.

---

## The whole firm in 5 sentences

1. There are **two halves**: a deterministic Python half (always-on, free, never judges — it scans, guards stops, alerts) and an LLM half (the committee — judgment, runs only when a session is open).
2. **One file is the law** — `config/limits.yaml` caps size, trades/day, and exposure; only you can change it.
3. **The flow never changes**: scanner finds a mover → analysts write memos → the bear can veto → *you* confirm → simulated fill → the journal records it.
4. **The bear's only job is to say no** — it's the adversary, on purpose.
5. **Stage 0's only goal is a track record** good enough to trust with real money later.

---

## Where we actually are (as of the last session, 2026-06-12)

- **Days run:** 3 (Jun 10–12). Day 3 ended early on a usage lock — no evening report was written.
- **Closed trades:** 2 — SMCI −$9.90 (stopped out, firm was right to pass), DNTH +$9.53 (first mechanical trailing-stop win). Net realized: **−$0.37** before commission.
- **Open positions:** CASY (simulated, ~+3–5%, healthy) and **F** (a real IBKR-paper "plumbing drill" — the exit manager already recommended closing it; it's still open).
- **Equity:** ~$1,724 on the last full day vs $1,700 start.
- **The big thing learned:** the firm discovered its dip-buying instinct loses money and momentum-pop buying wins (backtested), and rewired its doctrine accordingly. That's the system working.

---

## Graduation scorecard — your finish line, scored honestly

| Box (from `graduation.md`) | Status |
|---|---|
| ≥ 20 paper-account days | ❌ ~0 (sim days don't count; only the F drill touched the real paper account) |
| ≥ 15 closed trades | ❌ 2 of 15 |
| Positive P&L after $1/trade commission | ❌ −$0.37 before commission → negative after |
| Max drawdown ≤ 10% | ✅ fine so far (small sample) |
| Committee process beats Diego's overrides (or overrides folded in) | ⏳ **unresolved** — the firm's central open question |
| Zero order-path incidents in last 20 sessions | ⏳ too early (only 3 sessions exist; the F order was clean) |
| Validator catches geometry/sizing before the bear, 10 sessions running | ⏳ validator exists; streak not yet counted |
| Stops proven on the paper account (2 real executions) | ❌ 0 — every stop so far was simulated |
| Gateway uptime "boring" for a month | ❌ launchd not properly installed; a usage lock killed day 3 |
| Kill switch tested end-to-end | ⏳ not yet verified |
| Telegram alerts for fill / stop raised / stop hit / watcher down | ⏳ bot exists; not all paths confirmed |

The pattern: almost every unchecked box is blocked by one of two things — **not enough reps**, or **reliability that isn't boring yet.** Not missing features.

---

## What's actually blocking progress (the short list)

1. **Reps.** 2 closed trades, ~0 qualifying paper-account days. The track record is the bottleneck, and only running sessions fills it.
2. **Silent blindness.** The scanner has gone dark mid-session (budget), a usage lock ended day 3 early, and the daemons aren't installed as real background services. You can't yet trust it to run a day unattended — and "trustworthy unattended" is the whole point.
3. **Stops never proven for real.** Every stop that's fired was simulated. Two clean stop executions on the paper account is a named graduation gate, and it's at zero.
4. **The override question is open.** Are your discretionary calls better than the committee, or just early variance? A disciplined, well-logged run of sessions is the only thing that answers it.

**Two loose ends to tidy:** the F drill position (exit manager said close it) and the missing Jun 12 evening report.

---

## The one principle (so you can say no to yourself)

> **Every change must make a trustworthy track record arrive sooner.**
> Fewer, more reliable parts beat more parts. A boring session is a successful session. If a feature doesn't help you trust the firm with money, it waits.

The fast feature-building that got the project ahead of you is the instinct to rein in. For *this* goal, the work is reliability and reps — not capability.
