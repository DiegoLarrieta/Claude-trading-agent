---
name: backtest
description: Backtest mechanical trading rules (scanner triggers, stop/target/hold exits) over yfinance history and tune config/scanner.yaml with evidence. Use when the user says "/backtest", "test this strategy", "tune the scanner", or asks whether a rule would have worked historically.
---

# Backtest — evidence for the firm's mechanical rules

You run `scanner/backtest.py` to test rule-shaped strategies over daily history, then interpret results and (with the user's approval) tune `config/scanner.yaml`.

## Hard boundary

ONLY mechanical rules get backtested: trigger thresholds, stops, targets, holding periods. NEVER replay past dates through the committee agents — the model knows how history ended (lookahead bias), so LLM judgment is forward-tested via the daily journal only. If the user asks to "backtest the committee," explain this and offer the mechanical version.

## Running

```bash
.venv/bin/python scanner/backtest.py --years 2 --direction drop --move 5 --vol 2.5 --stop 5 --target 8 --hold 10
```

- `--direction drop` = buy big down moves (mean reversion); `pop` = buy big up moves (momentum)
- Trigger: |move| ≥ `--move`% vs prior close AND volume ≥ `--vol`× the 20-day average
- Exit: stop / target hit on daily closes (no intraday peeking — conservative), else exit after `--hold` days
- Default universe: 60 liquid $2B+ names; override with `--tickers AAPL,MSFT`

## Method (follow in order)

1. **Baseline first**: run the current `config/scanner.yaml` thresholds verbatim.
2. **One variable at a time**: sweep move (4/5/6/7), then vol (2/2.5/3), then exits. Compare `win_rate`, `avg_pnl_pct`, `expectancy_usd_per_200`, and the exit mix (many "time" exits = weak edge; many "stop" exits with high win rate = tight but profitable).
3. **Beware overfitting**: a parameter set that only wins in one sweep cell is noise. Prefer plateaus (neighbors also profitable) over peaks.
4. **Sample size matters**: under ~50 trades, say so — the result is anecdote, not evidence.
5. **Report honestly**: daily-close simulation understates real stops (intraday wicks would trigger more); say this in every report.
6. **Tuning the law**: present recommended `scanner.yaml` changes with the evidence table and get the user's explicit approval before editing. Config changes are human-gated.

## Output to the user

A short table of the sweep (params → trades / win% / avg / expectancy), one paragraph of interpretation, one concrete recommendation. No hype: negative expectancy results are just as valuable — they kill bad rules before the bear has to.
