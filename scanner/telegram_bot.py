#!/usr/bin/env python
"""Telegram bot — the firm's front door to Diego's phone. No LLM here.

Two roles:
  1. Outbound alerts: send_alert() is called by the watcher/monitor for
     stop hits, new candidates, and errors.
  2. Inbound commands (daemon mode): /status /pnl /halt /resume — accepted
     ONLY from the authorized chat id (the law: config/limits.yaml).

Credentials: TELEGRAM_BOT_TOKEN in .env (gitignored). Authorized chat id:
telegram_chat_id in config/limits.yaml — written once via `setup` mode.

Usage:
  telegram_bot.py setup    # discover your chat id after you /start the bot
  telegram_bot.py send "message"
  telegram_bot.py daemon   # long-poll for commands (run under launchd)
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
LIMITS = ROOT / "config" / "limits.yaml"
PORTFOLIO = ROOT / "journal" / "portfolio.json"


# ── pure logic (unit-tested) ────────────────────────────────────────


def parse_env(text: str) -> dict:
    """Minimal .env parser: KEY=VALUE lines, # comments, no quotes magic."""
    env = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def is_authorized(update: dict, allowed_chat_id: str | None) -> bool:
    """Only the single configured chat may command the firm."""
    if not allowed_chat_id:
        return False
    chat = ((update.get("message") or {}).get("chat") or {})
    return str(chat.get("id")) == str(allowed_chat_id)


def command_of(update: dict) -> str | None:
    text = ((update.get("message") or {}).get("text") or "").strip()
    return text.split()[0].lower() if text.startswith("/") else None


def format_status(portfolio: dict, prices: dict[str, float], halted: bool) -> str:
    lines = ["🛑 KILL SWITCH ON — no orders" if halted else "✅ firm operating"]
    total_cost = total_val = 0.0
    for p in portfolio["positions"]:
        price = prices.get(p["ticker"])
        cost = p["shares"] * p["fill_price"]
        total_cost += cost
        if price:
            val = p["shares"] * price
            total_val += val
            lines.append(f"{p['ticker']}: {p['shares']} @ {p['fill_price']} → {price:.2f} "
                         f"({(val - cost):+.2f} USD) stop {p['stop']}")
        else:
            lines.append(f"{p['ticker']}: {p['shares']} @ {p['fill_price']} (no price) stop {p['stop']}")
    if total_val and total_cost:
        lines.append(f"unrealized: {total_val - total_cost:+.2f} USD")
    lines.append(f"cash: ${portfolio['cash_usd']:.2f} [SIMULATED]")
    return "\n".join(lines)


# ── Telegram API shell ──────────────────────────────────────────────


def _token() -> str:
    env = parse_env(ENV_FILE.read_text()) if ENV_FILE.exists() else {}
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        sys.exit("TELEGRAM_BOT_TOKEN missing from .env")
    return token


def _api(method: str, **params):
    url = f"https://api.telegram.org/bot{_token()}/{method}"
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=35) as r:
        return json.loads(r.read().decode())


def _chat_id() -> str | None:
    import yaml
    cid = yaml.safe_load(LIMITS.read_text()).get("telegram_chat_id")
    return str(cid) if cid else None


def send_alert(text: str) -> bool:
    """Best-effort send to the authorized chat. Returns success."""
    cid = _chat_id()
    if not cid or not ENV_FILE.exists():
        return False
    try:
        return bool(_api("sendMessage", chat_id=cid, text=text).get("ok"))
    except Exception as e:
        print(f"WARN telegram send failed: {e}", file=sys.stderr)
        return False


def setup() -> None:
    """After Diego /starts the bot, find his chat id and print it."""
    updates = _api("getUpdates").get("result", [])
    chats = {}
    for u in updates:
        chat = ((u.get("message") or {}).get("chat") or {})
        if chat.get("id"):
            chats[chat["id"]] = chat.get("first_name") or chat.get("username") or "?"
    if not chats:
        print("No messages found — open your bot in Telegram, press START, send any message, retry.")
        return
    for cid, name in chats.items():
        print(f"chat_id: {cid}  (from: {name})")
    print("→ set this as telegram_chat_id in config/limits.yaml (human-only edit)")


def _handle(cmd: str) -> str:
    import yaml
    limits = yaml.safe_load(LIMITS.read_text())
    if cmd == "/halt":
        _set_kill_switch(True)
        return "🛑 KILL SWITCH ENGAGED — no orders (even simulated) until /resume."
    if cmd == "/resume":
        _set_kill_switch(False)
        return "✅ kill switch off — firm resumed."
    if cmd in ("/status", "/pnl", "/start"):
        pf = json.loads(PORTFOLIO.read_text())
        prices = {}
        try:
            import yfinance as yf
            prices = {p["ticker"]: yf.Ticker(p["ticker"]).fast_info.last_price
                      for p in pf["positions"]}
        except Exception:
            pass
        return format_status(pf, prices, limits.get("kill_switch", False))
    return "commands: /status /pnl /halt /resume"


def _set_kill_switch(value: bool) -> None:
    # surgical line edit — keeps comments/format of the law intact
    text = LIMITS.read_text()
    out = []
    for line in text.splitlines():
        if line.startswith("kill_switch:"):
            line = f"kill_switch: {'true' if value else 'false'}"
        out.append(line)
    LIMITS.write_text("\n".join(out) + "\n")


def daemon() -> None:
    print("telegram daemon up — long-polling for commands")
    offset = 0
    cid = _chat_id()
    while True:
        try:
            updates = _api("getUpdates", timeout=30, offset=offset).get("result", [])
            for u in updates:
                offset = u["update_id"] + 1
                if not is_authorized(u, cid):
                    continue  # silently ignore strangers
                cmd = command_of(u)
                if cmd:
                    _api("sendMessage", chat_id=cid, text=_handle(cmd))
        except Exception as e:
            print(f"WARN poll error: {e}", file=sys.stderr)
            time.sleep(10)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "setup"
    if mode == "send":
        ok = send_alert(" ".join(sys.argv[2:]) or f"ping {datetime.now(timezone.utc):%H:%M}")
        print("sent" if ok else "FAILED (token/chat_id configured?)")
    elif mode == "daemon":
        daemon()
    else:
        setup()
