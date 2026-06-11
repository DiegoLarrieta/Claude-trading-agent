# Graduation criteria — when the firm may trade real money (Stage 4)

Written 2026-06-10 (day 1 of simulation), while the question is still
hypothetical and heads are cool. The point of deciding now: going live
should be a calm checklist, not an itch after a lucky week.

ALL of the following must be true. The evening reporter tracks progress;
the final call is Diego's alone, made on a market-closed day.

## Track record (the journal must earn it)

- [ ] **≥ 20 trading days** on the IBKR paper account (real order routing,
      fake money) — local-sim days don't count toward this number.
- [ ] **≥ 15 closed trades** through the full pipeline, so the stats mean
      something.
- [ ] **Positive total P&L** over the paper-account period, after assuming
      $1/trade commission.
- [ ] **Max drawdown ≤ 10%** of starting equity during the period.
- [ ] **The committee process beats Diego's overrides** on the scoreboard,
      OR overrides have been formally folded into the process. If
      discretionary overrides are still outperforming the firm, the firm
      isn't ready to be trusted with autopilot money.

## Process safety (zero-tolerance items)

- [ ] **Zero unexplained order-path incidents** in the last 20 sessions —
      no order placed that wasn't proposed, confirmed, and validated;
      no stop that failed to execute; no portfolio-state corruption.
- [ ] **The deterministic validator catches geometry/sizing errors before
      the bear does** — the bear argues judgment, not arithmetic, for at
      least 10 consecutive sessions.
- [ ] **Stops proven on the paper account** — at least 2 real stop
      executions observed with acceptable slippage vs. the simulated
      assumption.
- [ ] **Gateway uptime is boring** — watcher + heartbeat ran a full month
      without a silent outage during market hours.

## Risk plumbing (must exist before the first live order)

- [ ] Live order path enforces `config/limits.yaml` IN CODE at order time
      (size, exposure, trades/day, kill switch, stop-below-entry).
- [ ] Kill switch tested: flipping `kill_switch: true` provably blocks
      orders end-to-end.
- [ ] First live config is TIGHTER than paper: `trade_size_usd: 100`,
      `max_trades_per_day: 1`, `max_open_positions: 2` for the first
      two weeks of live trading.
- [ ] Telegram alerts confirmed working for: fill, stop raised, stop hit,
      watcher down.

## The decision itself

When every box is checked, Diego reviews this file plus the full journal,
sleeps on it one night, and only then edits `config/limits.yaml` to
`mode: live` and unlocks the live port in `scanner/broker.py` — both
human-only actions, both in the same commit, with a journal entry saying
why today is the day.
