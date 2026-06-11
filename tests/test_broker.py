"""Unit tests for the broker link's safety locks — no network."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from broker import assert_paper_port, assert_paper_account, summarize_account


# ── THE LOCK: paper ports only ──────────────────────────────────────

def test_paper_ports_allowed():
    assert_paper_port(4002)  # IB Gateway paper
    assert_paper_port(7497)  # TWS paper


def test_live_gateway_port_refused():
    with pytest.raises(PermissionError, match="LIVE"):
        assert_paper_port(4001)


def test_live_tws_port_refused():
    with pytest.raises(PermissionError, match="LIVE"):
        assert_paper_port(7496)


def test_unknown_port_refused():
    with pytest.raises(PermissionError, match="not a recognized"):
        assert_paper_port(8080)


# ── paper account id check ──────────────────────────────────────────

def test_paper_account_id_allowed():
    assert_paper_account("DU1234567")


def test_live_looking_account_refused():
    with pytest.raises(PermissionError, match="paper"):
        assert_paper_account("U1234567")


# ── summary shaping ─────────────────────────────────────────────────

def test_summarize_account():
    tags = {"NetLiquidation": "1000000.0", "TotalCashValue": "999000.5",
            "BuyingPower": "4000000.0"}
    pos = [{"ticker": "AAPL", "shares": 10, "avg_cost": 200.0}]
    s = summarize_account(tags, pos)
    assert s["net_liquidation_usd"] == 1000000.0
    assert s["cash_usd"] == 999000.5
    assert s["positions"] == pos
    assert s["account_type"] == "paper"


# ── the mode lock (lock 2) ──────────────────────────────────────────

from broker import assert_order_path_enabled


def test_simulation_mode_blocks_orders():
    with pytest.raises(PermissionError, match="mode: paper"):
        assert_order_path_enabled({"mode": "simulation", "kill_switch": False})


def test_live_mode_blocks_orders_too():
    with pytest.raises(PermissionError, match="mode: paper"):
        assert_order_path_enabled({"mode": "live", "kill_switch": False})


def test_kill_switch_blocks_orders():
    with pytest.raises(PermissionError, match="kill_switch"):
        assert_order_path_enabled({"mode": "paper", "kill_switch": True})


def test_paper_mode_allows_orders():
    assert_order_path_enabled({"mode": "paper", "kill_switch": False})


def test_place_order_refused_end_to_end_in_current_config():
    """Integration: with the repo's real limits.yaml (mode: simulation),
    the order path must die at the mode lock before any network/socket."""
    from broker import place_paper_order
    with pytest.raises(PermissionError, match="mode: paper"):
        place_paper_order("NVDA", 1, 200.0, 185.0)
