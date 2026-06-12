# TODOS — deferred with context, not forgotten

## 1. Telegram phone-confirmation path
- **What:** Confirm/Reject inline buttons on Diego's phone so a trade proposal
  doesn't require being at the Mac.
- **Why:** "Usually at the Mac" is a lifestyle assumption baked into the
  current confirmation design; the day it breaks, proposals expire unanswered
  (10-min TTL) and the firm sits idle.
- **Current state:** `scanner/telegram_bot.py` exists, chat-ID-locked to
  Diego. The design doc (Execution & Confirmation Path) already specifies the
  full flow: the deterministic bot daemon receives the callback and re-validates
  caps/TTL/price-drift before acting; no LLM in the path.
- **Start here:** wire the proposal → Telegram message with buttons; callback
  handler updates proposal state; the loop honors phone-confirms identically
  to screen-confirms.
- **Depends on:** the /market-loop running stably for a few sessions first.
- **Added:** 2026-06-11 (plan-eng-review; deferred from decision D2).

## 2. Momentum book graduation (the deferred 5C)
- **What:** dedicated momentum sub-strategy — own scanner trigger profile,
  own sizing line in `config/limits.yaml`, own journal tag — so the momentum
  edge is measured (and capitalized) as its own book.
- **Why:** the 2026-06-11 backtest measured positive expectancy for confirmed
  pops; if the doctrine shipped tonight keeps producing vindicated candidates,
  it deserves dedicated capital rules. If not, clean evidence kills it.
- **Graduation gates:** (a) several live sessions of doctrine performance in
  the journal (trades tagged `setup: momentum-pop`), (b) /backtest re-runs
  with a slippage haircut and at least a second market regime, (c) explicit
  human approval — `limits.yaml` changes are law changes.
- **Depends on:** tonight's W6 doctrine change + journal setup-tagging.
- **Added:** 2026-06-11 (plan-eng-review; outside-voice findings #6 and #11
  define the evidence bar).
