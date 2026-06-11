---
name: start-trade
description: Boot the firm for a trading session - open IB Gateway for Diego to log in, start the daemons, verify every system (broker, watcher, heartbeat, telegram), and hand off ready-to-trade. Use when the user says "/start-trade", "start the trading day", "boot the firm", or "open the gateway".
---

# Start Trade — the firm's pre-flight checklist

You are booting the trading firm for a session. Run each step, report a
one-line ✅/❌ per system, and finish with a verdict: READY or what's missing.

## 1. Open IB Gateway for the human

```bash
ops/firm gateway
```

This launches the Gateway app (or reports it's already up). **Diego must
log in by hand** — paper mode, his credentials; the firm never stores or
types them. Tell him to log in, then poll until the link is live:

```bash
.venv/bin/python scanner/broker.py check
```

Retry every ~20s for up to 3 minutes while he logs in. If still down after
that, report ❌ broker and continue — a session without the broker is
legal (local sim still works); say what's degraded.

## 2. Start the daemons

```bash
ops/firm up && ops/firm status
```

Confirm: watcher process running (if within market hours; outside them it
exits by policy — say so), heartbeat loaded, telegram loaded.

## 3. Verify the broker link

```bash
.venv/bin/python scanner/broker.py status
```

Confirm the account id starts with "D" (paper) and report net liquidation.

## 4. Morning context

If no morning briefing exists for today, launch the **reporter** subagent
to write it (it covers positions, the thesis universe, and the calendar).

## 5. Verdict

One line per system: gateway / daemons / broker / briefing. Then either
**READY — say `/trading-day` (or `/paper-trade` for a no-broker session) to begin**
or the exact thing that's missing and who can fix it (you vs Diego).

Rules: never write to portfolio.json here; never place orders here; this
skill only boots and verifies. If `kill_switch: true`, say so and stop.
