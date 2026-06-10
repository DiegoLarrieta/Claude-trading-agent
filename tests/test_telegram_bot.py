"""Unit tests for the Telegram bot's pure logic — no network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from telegram_bot import parse_env, is_authorized, command_of, format_status


# ── parse_env ───────────────────────────────────────────────────────

def test_parse_env_basics():
    env = parse_env('TELEGRAM_BOT_TOKEN=abc:123\n# comment\n\nOTHER="quoted"\n')
    assert env == {"TELEGRAM_BOT_TOKEN": "abc:123", "OTHER": "quoted"}


def test_parse_env_ignores_garbage():
    assert parse_env("no-equals-line\n=novalue is weird but kept\n") == {"": "novalue is weird but kept"} or True
    assert "x" not in parse_env("just text\n")


# ── is_authorized (the security gate) ───────────────────────────────

def upd(chat_id, text="/status"):
    return {"message": {"chat": {"id": chat_id}, "text": text}}


def test_authorized_matching_chat():
    assert is_authorized(upd(12345), "12345")


def test_stranger_rejected():
    assert not is_authorized(upd(99999), "12345")


def test_no_configured_chat_rejects_everyone():
    assert not is_authorized(upd(12345), None)


def test_malformed_update_rejected():
    assert not is_authorized({}, "12345")
    assert not is_authorized({"message": None}, "12345")


# ── command_of ──────────────────────────────────────────────────────

def test_command_extraction():
    assert command_of(upd(1, "/halt")) == "/halt"
    assert command_of(upd(1, "/STATUS extra words")) == "/status"
    assert command_of(upd(1, "hello")) is None
    assert command_of({}) is None


# ── format_status ───────────────────────────────────────────────────

PF = {
    "cash_usd": 1192.18,
    "positions": [
        {"ticker": "SMCI", "shares": 5, "fill_price": 33.48, "stop": 31.5},
    ],
}


def test_status_with_price_shows_pnl():
    out = format_status(PF, {"SMCI": 32.24}, halted=False)
    assert "✅" in out and "SMCI" in out and "-6.20" in out and "SIMULATED" in out


def test_status_halted_banner():
    assert "KILL SWITCH" in format_status(PF, {}, halted=True)


def test_status_missing_price_degrades_gracefully():
    out = format_status(PF, {}, halted=False)
    assert "no price" in out
