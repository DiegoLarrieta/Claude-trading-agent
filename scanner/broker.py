#!/usr/bin/env python
"""IBKR broker link — deterministic, paper-account-locked.

Talks to a locally running IB Gateway / TWS over its API socket.
Reads are always allowed; ORDERS pass four locks stacked in series:
  1. port lock     — live ports (4001/7496) refused before any socket opens
  2. mode lock     — config/limits.yaml must say `mode: paper` (human-only edit)
  3. the validator — every order re-checked against the law + stop geometry
  4. order shape   — limit orders only, DAY time-in-force, no shorts
Stops stay managed by the firm's monitor (raise-only), not by IBKR.
Removing the port lock is a human-only, Stage 4 decision.

Usage:
  broker.py status      # connect, print account summary + positions
  broker.py check       # exit 0 if gateway reachable on a paper port
  broker.py order --ticker X --shares N --limit L --stop S [--horizon swing]
  broker.py orders      # list open orders
  broker.py cancel ID   # cancel an open order by orderId
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
ORDER_FILL_WAIT_S = 8  # how long `order` waits to report a fill before returning


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


def assert_order_path_enabled(limits: dict) -> None:
    """THE MODE LOCK. Orders only when the law says mode: paper.

    `simulation` = fills are local JSON, broker orders are a bug.
    `live` = Stage 4, which this module does not implement — the port
    lock above makes it physically unreachable anyway.
    """
    if limits.get("kill_switch"):
        raise PermissionError("kill_switch is ON — no orders of any kind")
    mode = limits.get("mode")
    if mode != "paper":
        raise PermissionError(
            f"limits.yaml mode is {mode!r} — broker orders require mode: paper "
            "(a human-only edit to the law)"
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


def connect(port: int, readonly: bool = True):
    assert_paper_port(port)
    from ib_async import IB

    ib = IB()
    ib.connect("127.0.0.1", port, clientId=CLIENT_ID, timeout=10, readonly=readonly)
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


def _require_gateway() -> int:
    port = find_gateway_port()
    if port is None:
        raise ConnectionError(
            "no IB Gateway/TWS found on paper ports "
            f"{sorted(PAPER_PORTS)} — is the gateway running and logged in?"
        )
    return port


def status() -> dict:
    ib = connect(_require_gateway())
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
        summary["connected_via"] = PAPER_PORTS[_require_gateway()]
        summary["account_ids"] = ib.managedAccounts()
        return summary
    finally:
        ib.disconnect()


def place_paper_order(ticker: str, shares: float, limit: float, stop: float,
                      horizon: str = "swing") -> dict:
    """Place a validated BUY limit order on the PAPER account.

    All four locks run before any order leaves this function. The stop is
    NOT sent to IBKR — it goes into the journal via the /trading-day
    validated path, and the monitor enforces it (raise-only).
    """
    import yaml
    sys.path.insert(0, str(ROOT / "scanner"))
    from validate_proposal import validate

    limits = yaml.safe_load((ROOT / "config" / "limits.yaml").read_text())
    assert_order_path_enabled(limits)                      # lock 2

    portfolio = json.loads((ROOT / "journal" / "portfolio.json").read_text())
    live = None
    try:
        import yfinance as yf
        live = yf.Ticker(ticker).fast_info.last_price
    except Exception as e:
        print(f"WARN live price unavailable ({e}) — drift check skipped", file=sys.stderr)
    proposal = {"ticker": ticker, "side": "buy", "shares": shares,
                "limit": limit, "stop": stop, "horizon": horizon}
    violations = validate(proposal, portfolio, limits, live_price=live)
    if violations:                                          # lock 3
        raise PermissionError("validator rejected the order:\n" +
                              "\n".join(f"  VIOLATION: {v}" for v in violations))

    from ib_async import LimitOrder, Stock
    ib = connect(_require_gateway(), readonly=False)        # lock 1 inside connect
    try:
        contract = ib.qualifyContracts(Stock(ticker.upper(), "SMART", "USD"))[0]
        order = LimitOrder("BUY", shares, limit, tif="DAY", outsideRth=False)  # lock 4
        trade = ib.placeOrder(contract, order)
        ib.sleep(ORDER_FILL_WAIT_S)
        st = trade.orderStatus
        return {
            "order_id": trade.order.orderId,
            "ticker": ticker.upper(),
            "con_id": contract.conId,
            "shares": shares,
            "limit": limit,
            "status": st.status,
            "filled": st.filled,
            "avg_fill_price": st.avgFillPrice or None,
            "account": "paper",
        }
    finally:
        ib.disconnect()


def open_orders() -> list[dict]:
    ib = connect(_require_gateway())
    try:
        return [
            {"order_id": t.order.orderId, "ticker": t.contract.symbol,
             "action": t.order.action, "qty": t.order.totalQuantity,
             "limit": getattr(t.order, "lmtPrice", None), "status": t.orderStatus.status}
            for t in ib.reqAllOpenOrders()
        ]
    finally:
        ib.disconnect()


def cancel_order(order_id: int) -> str:
    ib = connect(_require_gateway(), readonly=False)
    try:
        for t in ib.reqAllOpenOrders():
            if t.order.orderId == order_id:
                ib.cancelOrder(t.order)
                ib.sleep(2)
                return f"cancel sent for order {order_id} ({t.contract.symbol})"
        return f"no open order with id {order_id}"
    finally:
        ib.disconnect()


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    if mode == "check":
        port = find_gateway_port()
        if port:
            print(f"gateway listening on {port} ({PAPER_PORTS[port]})")
            return 0
        print("no gateway on paper ports", file=sys.stderr)
        return 1
    if mode == "order":
        import argparse
        ap = argparse.ArgumentParser(prog="broker.py order")
        ap.add_argument("--ticker", required=True)
        ap.add_argument("--shares", type=float, required=True)
        ap.add_argument("--limit", type=float, required=True)
        ap.add_argument("--stop", type=float, required=True)
        ap.add_argument("--horizon", default="swing")
        a = ap.parse_args(sys.argv[2:])
        print(json.dumps(place_paper_order(a.ticker, a.shares, a.limit, a.stop, a.horizon), indent=2))
        return 0
    if mode == "orders":
        print(json.dumps(open_orders(), indent=2))
        return 0
    if mode == "cancel":
        print(cancel_order(int(sys.argv[2])))
        return 0
    print(json.dumps(status(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
