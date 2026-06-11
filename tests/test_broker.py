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
