#!/usr/bin/env python
"""IBKR broker link — deterministic, READ-ONLY, paper-account-locked.

Talks to a locally running IB Gateway / TWS over its API socket.
Stage 3.5 scope: read account balance and positions from the PAPER
account. There is NO order-placement code in this file yet; when it
arrives (Stage 4), only the deterministic daemon may call it.

THE LOCK: live-account ports are refused at connect time, before any
socket is opened. Removing this lock is a human-only, Stage 4 decision.

Usage:
  broker.py status      # connect, print account summary + positions
  broker.py check       # exit 0 if gateway reachable on a paper port
No LLM anywhere in this file.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# IBKR convention: each client listens on a fixed port per mode.
PAPER_PORTS = {4002: "IB Gateway (paper)", 7497: "TWS (paper)"}
LIVE_PORTS = {4001: "IB Gateway (LIVE)", 7496: "TWS (LIVE)"}
CLIENT_ID = 17  # arbitrary fixed id so reconnects replace, not stack


# ── pure logic (unit-tested, no I/O) ────────────────────────────────


def assert_paper_port(port: int) -> None:
    """THE LOCK. Refuse anything that is not a known paper port."""
    if port in LIVE_PORTS:
        raise PermissionError(
            f"port {port} is {LIVE_PORTS[port]} — live trading is locked "
            "until Stage 4. This guard is removed by a human, never by code."
        )
    if port not in PAPER_PORTS:
        raise PermissionError(
            f"port {port} is not a recognized IBKR paper port "
            f"{sorted(PAPER_PORTS)} — refusing to connect."
        )


def assert_paper_account(account_id: str) -> None:
    """Belt AND suspenders: IBKR paper account ids start with 'D'."""
    if not account_id.upper().startswith("D"):
        raise PermissionError(
            f"account {account_id!r} does not look like a paper account "
            "(paper ids start with 'D') — refusing to proceed."
        )


def summarize_account(tags: dict[str, str], positions: list[dict]) -> dict:
    return {
        "account_type": "paper",
        "net_liquidation_usd": float(tags.get("NetLiquidation", "nan")),
        "cash_usd": float(tags.get("TotalCashValue", "nan")),
        "buying_power_usd": float(tags.get("BuyingPower", "nan")),
        "positions": positions,
    }


# ── I/O shell ───────────────────────────────────────────────────────


def connect(port: int):
    assert_paper_port(port)
    from ib_async import IB

    ib = IB()
    ib.connect("127.0.0.1", port, clientId=CLIENT_ID, timeout=10, readonly=True)
    accounts = ib.managedAccounts()
    for acct in accounts:
        assert_paper_account(acct)
    return ib


def find_gateway_port() -> int | None:
    """Probe known paper ports for a listening gateway. Never probes live ports."""
    import socket

    for port in PAPER_PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return port
    return None


def status() -> dict:
    port = find_gateway_port()
    if port is None:
        raise ConnectionError(
            "no IB Gateway/TWS found on paper ports "
            f"{sorted(PAPER_PORTS)} — is the gateway running and logged in?"
        )
    ib = connect(port)
    try:
        tags = {v.tag: v.value for v in ib.accountSummary() if v.currency in ("USD", "")}
        positions = [
            {
                "ticker": p.contract.symbol,
                "shares": p.position,
                "avg_cost": round(p.avgCost, 4),
            }
            for p in ib.positions()
        ]
        summary = summarize_account(tags, positions)
        summary["connected_via"] = PAPER_PORTS[port]
        summary["account_ids"] = ib.managedAccounts()
        return summary
    finally:
        ib.disconnect()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    if mode == "check":
        port = find_gateway_port()
        if port:
            print(f"gateway listening on {port} ({PAPER_PORTS[port]})")
            sys.exit(0)
        print("no gateway on paper ports", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(status(), indent=2))
