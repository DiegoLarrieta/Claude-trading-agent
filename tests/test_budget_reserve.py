"""Unit tests for the afternoon budget reserve — pure logic, no I/O.

Regression for 2026-06-12: the opening flood spent all 60 daily candidate
slots by mid-morning and the scanner ran blind into the afternoon while
SNDK ran +5.7% (second blindness incident in two days).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scanner"))

from scan import effective_daily_cap

CFG = {"afternoon_candidates": 25, "release_at_hour_et": 12}


def test_morning_cap_holds_back_the_reserve():
    assert effective_daily_cap(9.5, 75, CFG) == 50
    assert effective_daily_cap(11.99, 75, CFG) == 50


def test_full_allowance_unlocks_at_release_hour():
    assert effective_daily_cap(12.0, 75, CFG) == 75
    assert effective_daily_cap(15.5, 75, CFG) == 75


def test_missing_config_means_no_reserve():
    assert effective_daily_cap(9.5, 75, None) == 75
    assert effective_daily_cap(9.5, 75, {}) == 75


def test_reserve_larger_than_cap_floors_at_zero():
    assert effective_daily_cap(9.5, 10, {"afternoon_candidates": 99}) == 0


def test_default_release_hour_is_noon():
    assert effective_daily_cap(11.0, 75, {"afternoon_candidates": 25}) == 50
    assert effective_daily_cap(12.0, 75, {"afternoon_candidates": 25}) == 75
