# The firm's lessons — read by every agent at spawn

Curated institutional memory. The reporter distills new lessons each
evening and retires stale ones; agents READ this file, only the reporter
WRITES it. Hard cap: 25 active lessons — when full, the weakest lesson
must be retired to admit a new one. Each lesson is one rule + the day it
was earned. Retired lessons move to the bottom, never deleted.

## Active lessons

1. **(2026-06-10) Compute entry geometry from LIVE post-gap prices, never
   yesterday's levels.** A stop above the entry price means the numbers are
   stale. Cost: two broken memos (DNTH, CASY) on day one; now also enforced
   in code by `scanner/validate_proposal.py`.
2. **(2026-06-10) A dark data channel must be reported dark — never
   paraphrase other memos to fill it.** SMCI's "contrarian read" restated
   the price chart as sentiment and manufactured false conviction while
   Reddit was unreachable.
3. **(2026-06-10) Names with a documented accounting/governance history get
   a wider danger margin — the tail is fatter than the chart shows.** SMCI
   kept falling well past the stop (-12.6% vs the -5.9% the stop took);
   the bear's governance objection understated the danger, if anything.
4. **(2026-06-10) Blind dip-buying backtests NEGATIVE; selectivity is the
   entire edge.** All three day-one entries were "buy the sharp move"
   trades. The committee's job is saying no — "interesting but
   unconvincing" is a pass.
5. **(2026-06-10) Mechanism-identical competitor news is a direct hit, not
   sympathy noise.** When a competitor's same-mechanism drug fails on
   efficacy, that IS evidence about our candidate's drug (DNTH/riliprubart
   — both C1s inhibitors). Distinguish true sympathy moves from shared-
   mechanism risk before fading a gap.
6. **(2026-06-10) Track the Diego-vs-firm scoreboard daily.** All three
   day-one trades were discretionary overrides of unanimous committee
   PASSes. Whether the overrides or the committee are better calibrated is
   the firm's central open question — every memo should be written knowing
   the counterfactual will be scored.
7. **(2026-06-11) A silent scanner is indistinguishable from a quiet
   market — budget exhaustion must be loud.** `max_candidates_per_day=30`
   was fully consumed at the open; the scanner went blind from 9:50am while
   MU (+11.66%), SNDK (+14.50%), and ANET (+3.06%) ran unflagged, caught
   only because Diego happened to look. Fixed same-day (PR #16: 8/scan,
   60/day), but the firm needs an explicit "scanner is out of budget" alert,
   not silence.
8. **(2026-06-11) Momentum continuation has a measured positive edge; dip-
   buying measures negative — doctrine should follow the data, not
   instinct.** A mechanical backtest (buy +4% pop on 2.5x volume, stop 6/
   target 12/hold 20, 130 trades/2yr) returned +$4.47 expectancy per $200
   with every pop-cell positive; the mirror-image dip-buying rule returned
   -$0.51 at a 41% win rate. This extends lesson #4 (selectivity is the
   edge) with a directional finding: the firm's mean-reversion instinct has
   the sign backwards, and a momentum-book proposal is now on the table.
9. **(2026-06-17) Set stops at the level where the THESIS fails, not at the
   level where the EVENT pain stops.** VST was held through FOMC with a
   stop at $137 — the structural base-failure level — rather than tightened
   to avoid event volatility. FOMC passed without touching the stop; the
   position closed essentially flat and the thesis remains intact. A stop
   sized to event-avoidance would have either been triggered by normal
   intraday noise or placed so wide it was meaningless. Evidence: one clean
   binary-event hold; hypothesis open, not yet a full verdict.

## Retired lessons

(none yet)
