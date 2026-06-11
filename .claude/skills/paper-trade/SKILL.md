---
name: paper-trade
description: Run a fully LOCAL simulated trading day — scanner, committee, bear veto, simulated fills in journal/portfolio.json. Guaranteed to NEVER touch Interactive Brokers, regardless of any broker configuration. Use when the user says "/paper-trade", "simulate a day", or wants a no-broker session.
---

# Paper Trade — a trading day with the broker unplugged

This is the same standard operating procedure as `/trading-day`
(`.claude/skills/trading-day/SKILL.md`) with ONE absolute override:

**ALL fills are local simulations written to `journal/portfolio.json`.
Never run, import, or reference `scanner/broker.py`. Never open a
connection to IB Gateway/TWS, even read-only, even if `config/limits.yaml`
says a broker mode is available. The broker does not exist in this mode.**

Procedure:

1. Follow `.claude/skills/trading-day/SKILL.md` step by step — setup,
   scan, triage, committee, bear, proposal, human confirmation,
   position review, evening report.
2. Treat `mode` as `simulation` for the whole session, regardless of
   what `config/limits.yaml` says (this skill may only ever DOWNGRADE
   to simulation, never upgrade — `kill_switch: true` still halts
   everything).
3. Tag every fill `"simulated": true` (as the trading-day skill already
   requires) and mention "LOCAL SIM — broker untouched" when presenting
   proposals and in the evening report header.

Everything else — the law in `limits.yaml`, the bear's veto, human
confirmation of every trade, no invented market data — applies unchanged.
