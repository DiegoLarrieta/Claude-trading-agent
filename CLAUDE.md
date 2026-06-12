# Trade Agent — project instructions

A multi-agent trading firm running on Claude Code (Pro subscription, interactive sessions only). Design doc: `~/.gstack/projects/trade-agent/diego-no-branch-design-20260610-013601.md`. Currently **Stage 0: simulation** — no broker, simulated fills only.

## Hard rules (no exceptions)

- `config/limits.yaml` is THE LAW. No agent or prompt overrides it. Changing it is a human-only action.
- No LLM ever places real orders. At Stage 4 only the deterministic bot daemon will hold order permissions.
- NEVER set `ANTHROPIC_API_KEY` in this environment (it silently switches billing from subscription to API).
- Never write to `journal/portfolio.json` outside the validated path in the /trading-day skill.
- Market data comes from actual yfinance pulls — never from model memory. No invented numbers, ever.
- All Python runs through the project venv: `.venv/bin/python` (yfinance and pyyaml are installed there; bare `python3` lacks them).
- LLM judgment is forward-tested only. Never backtest the committee on past dates (lookahead bias — the model knows the endings). Mechanical rules may be backtested with deterministic scripts.
- IBKR access goes only through `scanner/broker.py`, which is READ-ONLY and hard-refuses live-account ports (4001/7496) in code. Removing that lock is a human-only Stage 4 action. `/paper-trade` runs a local-sim day that never touches the broker at all.

## Architecture in one breath

Deterministic scanner (Python, free) finds anomalies → candidate folders in `candidates/YYYY-MM-DD/TICKER-HHMM/` → triage (haiku) kills 80% → news/technical/sentiment analysts write memos in parallel → the bear (sonnet) writes numbered objections and holds a VETO → head trader (sonnet) answers objections by number and proposes a limit order → bear final pass (any SUSTAIN = veto) → human confirms → simulated fill in `journal/portfolio.json`. The memo folder is the audit trail.

## Conventions

- Agents live in `.claude/agents/` — one file per role, scoped tools, models per `config/agents.yaml`.
- Memos: `candidate.json`, `triage.md`, `news.md`, `technicals.md`, `sentiment.md`, `bear.md`, `decision.md`, `bear-final.md`.
- Journal: `journal/YYYY-MM-DD/{morning-briefing,evening-report}.md`; positions in `journal/portfolio.json`.
- `journal/lessons.md` is the firm's institutional memory: every agent reads it at spawn; ONLY the reporter writes it (1-2 distilled lessons max per evening, 25-lesson cap, retired never deleted).
- Every analyst memo cites sources with channel + URL. Reddit-only narratives are flagged as warnings.
- Run a session with the `/trading-day` skill, or as a self-pacing tick loop with `/market-loop` (same procedure, tick-shaped; `/pause` to go deliberately dark). The user (Diego) is new to trading: explain trading terms briefly on first use; he confirms every trade.

## Roadmap context

Stage 0 simulation (now) → 1 Telegram/email plumbing → 2 Python watcher daemon → 3 full committee automation → 4 IBKR via MCP + real money (small, capped). IBKR connects only after the simulated journal earns trust.
