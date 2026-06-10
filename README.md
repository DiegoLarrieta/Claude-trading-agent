# Claude Trading Agent

A personal, multi-agent **AI trading firm** that runs entirely on a Claude Code subscription — no LLM API keys, no cloud infrastructure. It watches the whole US market during open hours, investigates opportunities like a team of analysts, and proposes trades that a human confirms with one tap. Real money only enters after the firm has proven its judgment in simulation.

> **Status: Stage 0 — simulation playground.** No broker is connected. All fills are simulated at real market prices.

## The idea

Instead of one AI making trading calls, this is an **org chart**: specialist agents with scoped tools that communicate through written memos, an adversarial risk manager whose only job is to kill bad trades, and a head trader who can propose but never execute. The human (Diego) is the final gate on every trade.

```
                       ┌─────────────────────────────────────────────┐
 MARKET (live)         │              THE FIRM (Claude Code)         │
┌──────────────┐       │                                             │
│ Python       │ candi-│  Triage ──► News ─┐                         │
│ scanner      │ dates │  (haiku)  Technical ├─► Bear ──► Head      │
│ (no LLM,     ├──────►│           Sentiment┘   (veto!)   Trader     │
│ free, all    │       │            parallel              (proposes) │
│ day)         │       │                                      │      │
└──────────────┘       └──────────────────────────────────────┼──────┘
                                                               ▼
                                          Telegram alert ──► Diego taps Confirm
                                                               ▼
                                          Deterministic bot places the order
                                          (caps, TTL, drift checks — no LLM)
```

## The firm (agent roster)

| Agent | Model | Tools | Job |
|---|---|---|---|
| **Scanner** | none (Python) | yfinance, news/Reddit polling | Watches every sector all day for anomalies (big moves, volume spikes); emits candidate folders. Free — no tokens. |
| **Triage analyst** | haiku | candidate file only | First look. Kills ~80% of candidates in one short call. |
| **News analyst** | haiku | web search/fetch, SEC EDGAR | *Why* did it move? Real catalyst or noise? Cites every source. |
| **Technical analyst** | haiku | market data (read-only) | Trend, levels, volume — falling knife or buy window? |
| **Sentiment analyst** | haiku | Reddit (public API) | Crowd positioning. Euphoria counts *against* a trade. |
| **Risk manager (the bear)** | sonnet | portfolio, configs, all memos, search | Adversarial by design — argues against every trade as numbered objections. **Holds a veto.** |
| **Head trader** | sonnet | memos, proposal channel | Answers the bear's objections, sizes the position within the caps, writes the proposal. **Cannot execute.** |
| **Reporter** | sonnet | portfolio, logs, email/Telegram | Pre-market briefing + after-market journal (trades, P&L, considered-and-passed log). |

Agents communicate through **memo files** in a per-candidate folder — the full decision trail of every trade lives on disk and is auditable forever:

```
candidates/2026-06-10/NVO-1432/
  candidate.json   ← scanner: what triggered
  news.md          ← news analyst
  technicals.md    ← technical analyst
  sentiment.md     ← sentiment analyst
  bear.md          ← risk manager: numbered objections
  decision.md      ← head trader: rebuttals + prepared order
  bear-final.md    ← bear's APPROVE/SUSTAIN per objection (SUSTAIN kills it)
```

## The law (safety model)

The LLM proposes; **deterministic code disposes**. Hard limits live in `config/limits.yaml` and are enforced by plain Python at order time — no agent can override them:

- Max $ per trade, max trades/day, max total exposure
- Proposal TTL (stale proposals re-trigger analysis) and price-drift abort
- Telegram confirmations accepted only from one hard-coded chat ID
- `/halt` kill switch; external dead-man's switch if the machine goes silent
- **No LLM ever holds order-placement permissions** — only the bot daemon does

## Roadmap (money enters last)

| Stage | What ships | Broker? |
|---|---|---|
| **0 — Simulation playground** *(now)* | Full pipeline on live market data, simulated fills in `portfolio.json`, evening P&L report | No |
| **1 — Reporter + plumbing** | Telegram bot, email, scheduled morning/evening jobs, on-demand `analyze TICKER` | No |
| **2 — Scanner + triage** | Python watcher daemon, alert-only discovery, cooldowns, heartbeat | No |
| **3 — Full committee** | All analysts + bear veto + head trader memos | No |
| **4 — IBKR + one-tap execution** | IB Gateway + IBKR MCP, real orders behind hard caps + Telegram Confirm, tiny sizes | **Yes** — gated on the simulated track record |

## How it runs (Claude Code, Pro plan)

- Each role is a **subagent** in `.claude/agents/` (system prompt + tool allowlist). Procedures are **skills** (`/trading-day`, `/morning-briefing`, ...).
- During market hours, **one interactive Claude Code session** runs a recurring loop, picking up candidates the scanner drops into `candidates/inbox/` — interactive sessions bill against the subscription, not the headless credit pool.
- Strategy rules are backtested with deterministic scripts over yfinance history. The committee's *judgment* is forward-tested only — the simulated trading journal is the track record (replaying famous past dates through an LLM is invalid: it already knows the endings).
- `ANTHROPIC_API_KEY` must **never** be set in this environment.

## Disclaimers

Personal project, not financial advice, not a product. An LLM trading firm is a diligent analyst, not an oracle — its edge is coverage and discipline, not prediction. Every trade is confirmed by a human, and the design assumes the model will sometimes be confidently wrong (that's what the bear, the caps, and the journal are for).
