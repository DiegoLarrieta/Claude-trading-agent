# Position Review — 2026-06-17
Exit manager / pre-FOMC review (written 12:08 ET, FOMC statement at 14:00 ET)

Firm lessons consulted: lessons.md (active lessons 1-8)
Mechanical limits consulted: config/limits.yaml (exits.swing profile)

---

## VST (entry $159.73 all-in basis, now $161.60, +$1.87 / +1.2%, stop $137.00)

Horizon: swing (portfolio.json field: "swing"; limits.yaml swing exit profile applies)
Mechanical protections active: stop at $137.00 — no breakeven trigger yet (requires +8% / ~$172.47), no trail trigger yet (requires +12% / ~$178.90). Position is in the unprotected zone; stop remains at the original structural level.

THESIS WAS: IG-rated, record-EBITDA power producer named preferred provider in $10B Nvidia/KKR Helix AI-infra JV; base breakout. Exploratory test of a fundamentals-filtered dip-buy vs the negative-expectancy backtest.

WHAT CHANGED:

New since entry (2026-06-16):

- Bernstein initiated VST Outperform with a $187 price target on or around June 17, 2026, calling rising power demand a "double-barreled earnings event" for Vistra. This is an additive sell-side catalyst layered on top of the existing Seaport ($230) and BMO ($245) raises. Source: Stocktwits top headline (author 107,767 followers); Bernstein initiation article dated June 17, 2026 — https://stocktwits.com/news-articles/markets/equity/vst-stock-gains-overnight-bernstein-calls-rising-power-demand-double-barreled-earnings-event-for-vistra/cZK0loPR7Ic

- FOMC at 14:00 ET today: Rate held unchanged at 3.50-3.75% (97% probability priced in as of June 13; confirmed hold per StockTitan preview). The critical variable is the dot plot and Warsh's press conference tone (14:30 ET). Market consensus going in: the single projected cut from March dots is likely removed, and 3 of 12 FOMC members may project rate hikes this year. A "hawkish hold" — hold rate but drop cut projections and signal higher-for-longer — is the adverse scenario for VST as a ~$12B net-debt IPP. Sources: https://intellectia.ai/blog/fed-interest-rate-decision-june-2026; https://www.stocktitan.net/articles/fed-rate-decision-june-17-2026; https://www.cbsnews.com/news/federal-reserve-interest-rates-kevin-warsh-june-2026/

- Intraday today: VST opened $158.57, touched $161.74 high, currently $161.60. It is holding above yesterday's close on the Bernstein headline. Low so far: $157.21 — still above our $156.50 decision-level limit price and well above the stop.

- Stocktwits: 30 messages, 14 bullish / 3 bearish / 13 untagged. Bullish ratio of tagged: 82%. Top posts are institutional-tone commentary (the Bernstein headline and AI power demand narrative). No sign of crowding or retail euphoria — crowd shift is net positive since entry.

- No earnings event within 5 sessions (original days_to_earnings: 51; now ~49). Ex-dividend June 22 is within the next 5 sessions — this is NOT an earnings binary, but a mechanical ex-div drop equal to the declared dividend will occur if we hold through June 22. That gap-down should NOT be mistaken for thesis deterioration and should NOT trigger a stop review at the time.

Nothing material has changed against the thesis. The Bernstein initiation is an incremental tailwind.

FOMC is the open variable. FOMC outcome (hold + dots) is unknown as of this writing. The bear's FOMC objection (filed 2026-06-16, NOTED/waived at exploratory size) is now live. The wide $137 stop — set deliberately at the structural base-failure level to survive this event — remains the firm's answer.

Forward-looking re-test of the thesis: Would today's facts justify buying VST for the first time? Yes — the Helix JV thesis is intact, a new Bernstein initiation adds institutional sponsorship, record EBITDA and IG ratings are unchanged, earnings are 7 weeks away, and the stock is recovering from a structural base. The geometry (dip-to-support) still carries the Lessons #4/#8 negative-expectancy flag from the undifferentiated backtest, but the fundamentals filter is working exactly as designed and nothing has invalidated it.

RECOMMENDATION: HOLD

REASON: The original thesis is intact and has gained an incremental tailwind (Bernstein Outperform/$187 initiation this morning). The FOMC binary is the only material risk on the horizon and the committee explicitly priced it in when it set the stop at the structural base-failure level ($137, approximately 15% below current price) rather than a tight noise-filter level. The exploratory size ($12.46 maximum loss) was authorized precisely to carry this kind of known binary. Tightening the stop into the event would largely defeat the structural-stop logic: a hawkish FOMC can move VST 1-2 ATRs ($6.50-$13.00) intraday, and a stop tighter than $148-$150 would likely be hit on a whipsaw before any real thesis failure. Closing locks roughly breakeven (current gain ~$1.87 minus $1.00 IB exit commission = ~$0.87 realized) and forfeits a thesis that just attracted a new sell-side sponsor this morning — a poor trade of potential upside for a realized gain of less than a dollar. The honest forward case: if Warsh's statement and dots are benign (or even mildly hawkish as priced), VST should hold its base and the position carries forward on the original plan; if FOMC is severely hawkish and the stock gaps toward the base, the $137 stop does its structural job. The committee accepted this trade-off at entry; nothing since has changed the calculus materially enough to override it.

---

## F (entry $14.23, now $14.47, +$0.24 / +1.7%, stop $14.23)

Horizon: day (portfolio.json field; however, position has been open since 2026-06-11 — six sessions)

THESIS WAS: PLUMBING DRILL — first order through the IBKR paper pipeline; not a thesis trade.

WHAT CHANGED: DATA UNAVAILABLE — no thesis to re-test and no news searched, because this was never a thesis trade. The position has no investment rationale beyond testing order plumbing.

FOMC CALENDAR: F is a US automaker with significant debt and consumer-credit sensitivity — it is rate-sensitive. However, since this is not a thesis trade, the question of holding through FOMC does not arise as a thesis judgment. It arises as a cleanliness question.

RECOMMENDATION: CLOSE

REASON: This was a plumbing drill opened 2026-06-11 with a "day" horizon — it has now been open six sessions, which is a question in itself (as the review prompt flags). There is no forward-looking thesis that would justify holding it as a first-time buy today. The stop is at breakeven ($14.23), so the position is riskless on the downside, but riskless does not mean worth holding indefinitely. It consumes one of five available position slots (config/limits.yaml max_open_positions: 5) and creates journal noise. The FOMC reaction will move F given its debt and consumer-finance exposure; this is a new, unanalyzed risk for a position with no analytical basis. Close it cleanly and free the slot.

---

## Mechanical status summary

VST: No mechanical exit triggers have been reached. The swing exit profile requires +8% from entry ($159.73) to trigger the breakeven stop move — that threshold is $172.51. Current price $161.60 is $10.91 short of the breakeven trigger. All stops are at their original set levels; no adjustments are pending or legally permissible downward.

F: Stop is at breakeven $14.23. The day-horizon breakeven trigger (4%) was already reached (high_water $14.805 per portfolio.json, which is +4.1% above $14.23 fill price). A trailing stop should already be active per the day-exit profile (trail_trigger_pct 6%, trail_distance_pct 3%). At the $14.47 current price, the position is $0.24 above breakeven — trivially small; CLOSE recommendation stands regardless.

---

*Sources consulted: yfinance live data (12:08 ET); Stocktwits sentiment_feed.py; Bernstein initiation via Stocktwits headline; FOMC context via intellectia.ai, StockTitan, CBS News, Commerzbank/FXStreet; Vistra thesis memos in candidates/2026-06-16/VST-1142/.*
