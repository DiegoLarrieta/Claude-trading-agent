# Claude Trading Agent

A personal, multi-agent **AI trading firm** that runs on a Claude Code subscription — no LLM API keys, no cloud infrastructure. A deterministic Python daemon watches the US market all day for free; when something dislocates, a committee of specialist Claude agents investigates it like a research desk, an adversarial risk manager tries to kill the trade, and a head trader proposes an order that **a human confirms before any fill**. Real money enters only after the simulated journal earns trust.

> **Status — Stage 0/2, paper mode.** `config/limits.yaml` is set to `mode: paper`: orders can route to an **IBKR paper account** (fake money, real order plumbing), and the always-on **watcher daemon** is built and running. The live-money port is still hard-locked in code. Most days still run as pure local simulation via `/paper-trade`.

---

## The idea

Instead of one model making trading calls, this is an **org chart**. Specialist agents with narrowly scoped tools communicate through written memos on disk. An adversarial risk manager (the "bear") exists only to argue against trades and holds a veto. A head trader can propose but can never execute. Hard limits live in a config file that is treated as law and enforced by plain Python — no prompt can override it. Diego (the human) is the final gate on every trade.

```
                          THE FIRM (Claude Code, interactive session)
 MARKET (live, yfinance)  ┌────────────────────────────────────────────────────┐
┌──────────────────────┐  │  inbox ─► Triage ─► News ─────┐                     │
│  Watcher daemon       │ candi-     (haiku)   Technical   ├─► Bear ──► Head     │
│  (Python, no LLM,     │ dates│              Sentiment ───┘  (VETO!)   Trader   │
│  free, all day):      ├─────►│               (parallel analysts)     (proposes)│
│   • scans for movers  │  │                                              │      │
│   • guards stops      │  │   validate_proposal.py (the law, in code) ◄──┘      │
│   • watch-levels      │  └──────────────────────────────┬───────────────────--┘
│   • heartbeat         │                                 ▼
└──────────────────────┘            Diego confirms ──► simulated fill in portfolio.json
                                    (or, in paper mode, a port-locked IBKR paper order)
```

---

## The firm (agent roster)

Each agent is a subagent in `.claude/agents/` with its own system prompt and a scoped tool allowlist. Model assignments live in `config/agents.yaml` and have been tuned by experience (see note below the table).

| Agent | Model | Job |
|---|---|---|
| **Scanner / watcher** | none (Python) | The firm's always-on eyes. Pulls real movers from yfinance, applies universe + trigger rules, and drops candidate folders into the inbox. Also guards stops and watch-levels. Free — no tokens. |
| **Triage analyst** | haiku | First-pass filter on every new candidate. Kills ~80% in one cheap, fast call. |
| **News analyst** | sonnet | *Why* did it move — real catalyst or noise? Searches wires, sector press, SEC EDGAR filings. Cites every source with channel + URL. |
| **Technical analyst** | sonnet | Trend, levels, volume. Computes indicators from raw yfinance bars. Falling knife or buy window? |
| **Sentiment analyst** | haiku | Crowd positioning via Stocktwits. **Euphoria counts against a trade.** Reddit-only narratives are flagged as warnings. |
| **Risk manager (the bear)** | sonnet | Adversarial by design. Writes numbered objections against every trade and **holds a veto**. Does a final APPROVE/SUSTAIN pass — any SUSTAIN kills the trade. |
| **Head trader** | sonnet | Answers the bear's objections by number, sizes the position within the caps, writes the proposal. **Cannot execute.** |
| **Exit manager** | sonnet | The committee for everything *after* the fill. Re-tests the thesis on open positions: hold / tighten stop / close. The human confirms any close. |
| **Reporter** | sonnet | Writes the pre-market briefing and after-market evening journal. Is the **only** writer of `journal/lessons.md`. Trades nothing. |

> **Why some analysts run on sonnet, not haiku:** model seats are promoted when haiku demonstrably fails. The technical analyst was promoted on day one (haiku botched stop/direction arithmetic in 2 of 3 memos); the news analyst was promoted 2026-06-12 after haiku misread catalysts two days running. The bear caught both — but the bear is the last line, not the first. This history lives in `config/agents.yaml`.

### The memo trail

Agents don't chat — they leave written memos in a per-candidate folder, so the full decision trail of every trade is on disk and auditable forever:

```
candidates/2026-06-10/NVO-1432/
  candidate.json   ← scanner: what triggered (real yfinance numbers)
  triage.md        ← triage analyst: pursue or kill
  news.md          ← news analyst: catalyst, with sources
  technicals.md    ← technical analyst: trend & levels
  sentiment.md     ← sentiment analyst: crowd positioning
  bear.md          ← risk manager: numbered objections
  decision.md      ← head trader: rebuttals by number + the proposed order
  bear-final.md    ← bear's APPROVE/SUSTAIN per objection (any SUSTAIN = killed)
```

---

## The law (safety model)

The LLM proposes; **deterministic code disposes.** `config/limits.yaml` is THE LAW — no agent, prompt, or model may override it, and changing it is a human-only action. It is enforced in plain Python (`scanner/validate_proposal.py`), which re-derives every limit from the config and the live portfolio rather than trusting any memo.

Current caps (mirroring the real ~$1,700 account):

| Limit | Value |
|---|---|
| `mode` | `paper` (simulation / paper / live) |
| `trade_size_usd` | $200 per trade (head trader may propose less, never more) |
| `max_trades_per_day` | 3 |
| `max_open_positions` | 5 |
| `max_total_exposure_usd` | $1,400 (~82% of the account — always keep dry powder) |
| `order_type` | limit only — never market |
| `proposal_ttl_minutes` | 10 (expired proposals re-trigger analysis) |
| `max_price_drift_pct` | 1.0 (abort if price moved more since the proposal) |
| `allow_short_selling` / `allow_options` | false / false |
| `telegram_chat_id` | the one chat the bot obeys or alerts |
| `kill_switch` | `false` — flip to `true` to block all orders, even simulated |

**Mechanical exit rules** are also law and also enforced by code, not judgment. Every position declares a horizon at buy time and is escalated by that profile. Stops only ever move **up** — never widened, never lowered.

| Horizon | Breakeven trigger | Trail trigger | Trail distance |
|---|---|---|---|
| `day` (hours–2 days) | +4% | +6% | 3% |
| `swing` (days–weeks, default) | +8% | +12% | 6% |
| `core` (months) | +20% | +30% | 15% |

### The IBKR broker locks

`scanner/broker.py` is the *only* path to Interactive Brokers, and it is read-only by default. Orders pass four locks stacked in series:

1. **Port lock** — live ports (4001 / 7496) are refused before any socket opens. Removing this is a human-only Stage 4 action.
2. **Mode lock** — `config/limits.yaml` must say `mode: paper` (a human-only edit).
3. **The validator** — every order is re-checked against the law and the stop geometry.
4. **Order shape** — limit orders only, DAY time-in-force, no shorts.

`/paper-trade` bypasses the broker entirely: a fully local simulated day that can never touch IB Gateway regardless of configuration.

---

## The always-on infrastructure (the deterministic half)

None of these files contain an LLM. They are the firm's reflexes — they run whether or not a Claude session is awake.

| File | What it does |
|---|---|
| `scanner/watcher.py` | The daemon. During market hours: scans every `poll_interval_seconds`, queues new candidates, checks stops, checks watch-levels, writes a heartbeat each tick. Runs under launchd. |
| `scanner/scan.py` | The deterministic scanner core — top movers filtered by `universe`/`triggers`, with pre-triage kills (e.g. an earnings-window move *is* the earnings reaction). |
| `scanner/monitor.py` | Position stop monitor. On a breach, simulates a conservative exit at the stop price and alerts. |
| `scanner/inbox_queue.py` | Two-file, append-only candidate queue (`pending.jsonl` written by the watcher, `processed.jsonl` by the session) — no locks, crash-recovery for free. |
| `scanner/watch_levels.py` | Committee-set price tripwires ("re-review NVDA if it touches 196"). Fires at most once/day. An alert means *convene the review*, never *buy*. |
| `scanner/session_state.py` | Tracks the LLM session: active / paused / ended, plus a session heartbeat so a wedged session becomes loud, not silently dark. |
| `scanner/heartbeat_check.py` | Dead-watcher + dead-gateway detector (launchd, every 5 min). Alerts loudly if stop protection or the broker link goes missing during market hours. |
| `scanner/telegram_bot.py` | The firm's front door to Diego's phone — outbound alerts + inbound `/status` `/pnl` `/halt` `/resume`, accepted only from the authorized chat id. |
| `scanner/sentiment_feed.py` | Stocktwits fetcher — neutral, numeric crowd metrics for the sentiment analyst (it measures the crowd, never interprets it). |
| `scanner/validate_proposal.py` | The law in code — every proposal must pass before a human ever sees it. |
| `scanner/backtest.py` | Mechanical-rule backtester over yfinance history. Rules only — never the committee. |
| `scanner/broker.py` | The port-locked IBKR link (see above). |
| `ops/firm` | Human override for the daemons: `up` / `down` / `on` / `status` / `gateway`. The human always wins. |
| `ops/install-watcher.sh` | Installs the launchd plists (watcher, telegram, heartbeat). |

There are **162 tests** (`tests/`, run via `pytest`) and a GitHub Actions CI workflow (`.github/workflows/ci.yml`) covering the deterministic machinery — scanner, queue, validator, broker locks, exits, watch-levels, session state, heartbeat, budget reserve, and more.

---

## How you run it (the skills)

Procedures are **skills** in `.claude/skills/`. Invoke them by name in a Claude Code session:

| Skill | What it does |
|---|---|
| `/trading-day` | The standard operating procedure: drain the inbox, run candidates through the committee with the bear's veto, record simulated fills, produce the evening report. Step 4 is the **only** path that writes `journal/portfolio.json`. |
| `/market-loop` | The same firm shaped as a self-pacing tick loop — wakes itself every few minutes, does a bounded amount of work, guards stops, winds down at the close. |
| `/paper-trade` | A fully local simulated day with the broker unplugged — guaranteed never to touch IBKR. |
| `/start-trade` | Pre-flight checklist: open IB Gateway for Diego to log in, start the daemons, verify every system, hand off READY (or report what's degraded). |
| `/pause` | Deliberate blindness + honest catch-up. Records the pause, explains exactly what's still guarded vs. going dark, and runs a deterministic resume-brief afterward. |
| `/backtest` | Evidence for mechanical rules — sweep trigger/exit parameters over history, one variable at a time, and tune `config/scanner.yaml`. |

A few operating principles baked into these skills:

- The watcher is the **sole** scanner — the interactive session never scans the market itself; it consumes the inbox queue.
- The scanner has a **budget reserve**: the morning open always floods, so slots are held back until midday or the afternoon goes blind (this bug bit twice — missed MU +9%, SNDK +13% — and is now configured in `scanner.yaml`).
- Stop protection is deterministic and never pauses while the Mac is awake. `/pause` only darkens the *LLM* side. If the lid closes, **everything** stops, and an external dead-man's switch (healthchecks.io) is what notices the silence.

---

## Institutional memory

`journal/lessons.md` is the firm's accumulated wisdom — every agent reads it at spawn, and **only the reporter writes it** (1–2 distilled lessons per evening, 25-lesson cap, retired ones moved to the bottom, never deleted). It already encodes hard-won rules like *compute entry geometry from live post-gap prices, never yesterday's levels* and *blind dip-buying backtests negative — selectivity is the entire edge.*

`config/universe.yaml` is Diego's declared circle of competence (software engineer; the AI buildout stack) — names the firm chooses to *know*, watched with more sensitive triggers and, deliberately, scrutinized *harder* by the bear because familiarity is a bias.

---

## Roadmap (money enters last)

| Stage | What ships | Broker? |
|---|---|---|
| **0 — Simulation** | Full pipeline on live data, simulated fills in `portfolio.json`, evening P&L | No |
| **1 — Plumbing** ✅ | Telegram bot, alerts, scheduled jobs, session/heartbeat machinery | No |
| **2 — Watcher daemon** ✅ | Always-on Python scanner, inbox queue, stop monitor, watch-levels, dead-man checks | No |
| **3 — Full committee** ✅ | All analysts + bear veto + head trader memos + exit manager | No |
| **4 — IBKR + one-tap execution** *(in progress)* | IB Gateway, port-locked paper orders today; live money behind hard caps + Telegram Confirm, tiny sizes, **gated on the simulated track record** | Paper now, live last |

The criteria for going live are written down *now*, while heads are cool, in `config/graduation.md`: ≥20 paper-account days, ≥15 closed trades, positive P&L after commission, ≤10% drawdown, zero order-path incidents, and a tighter-than-paper first live config. Every box must be checked; the final call is Diego's alone, on a market-closed day, sleeping on it one night first.

Two known follow-ups are parked with full context in `TODOS.md`: the Telegram phone-confirmation path, and a graduated momentum sub-book once the doctrine proves itself in the journal.

---

## Conventions & hard rules

- All Python runs through the project venv: `.venv/bin/python` (yfinance + pyyaml live there; bare `python3` does not).
- Market data comes from **actual yfinance pulls** — never from model memory. No invented numbers, ever.
- LLM judgment is **forward-tested only** — never backtested on past dates (the model knows the endings). Mechanical rules may be backtested with deterministic scripts.
- `ANTHROPIC_API_KEY` must **never** be set in this environment (it silently switches billing from the subscription to the API).
- Interactive sessions only — they bill against the Pro subscription, not the headless credit pool.

---

## Disclaimers

Personal project, not financial advice, not a product. An LLM trading firm is a diligent analyst, not an oracle — its edge is coverage and discipline, not prediction. Every trade is confirmed by a human, and the whole design assumes the model will sometimes be confidently wrong. That's exactly what the bear, the caps, the validator, and the journal are for.
