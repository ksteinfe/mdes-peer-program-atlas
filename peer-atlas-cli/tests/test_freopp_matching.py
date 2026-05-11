"""Unit tests for FREOPP matching pure functions."""

from __future__ import annotations

import pytest

from peer_atlas_cli.commands.classify_freopp import (
    _cip_to_freopp_int,
    _cip_family,
    _tuition_compatible,
    prioritize_candidates,
)


# ── _cip_to_freopp_int ──────────────────────────────────────────────────────

@pytest.mark.parametrize("code,expected", [
    ("50.0401", 5004),   # design — standard case
    ("04.0201", 402),    # architecture — leading zero stripped
    ("11.0101", 1101),   # computer science
    ("14.0101", 1401),   # engineering
    ("52.1201", 5212),   # management info systems
    ("09.0702", 907),    # digital communication — note: 3-digit result
])
def test_cip_to_freopp_int_valid(code, expected) -> None:
    assert _cip_to_freopp_int(code) == expected


@pytest.mark.parametrize("code", ["", None, "50", "50.0", "invalid", "XX.YYYY"])
def test_cip_to_freopp_int_invalid(code) -> None:
    assert _cip_to_freopp_int(code) is None


# ── _cip_family ─────────────────────────────────────────────────────────────

def test_cip_family() -> None:
    assert _cip_family("50.0401") == 50
    assert _cip_family("04.0201") == 4
    assert _cip_family("11.0101") == 11
    assert _cip_family("bad") is None


# ── _tuition_compatible ─────────────────────────────────────────────────────

def _prog(cost_usd=None, semesters=None):
    return {
        "degree_cost": {"comparison_cost_usd": cost_usd},
        "duration": {"length_in_berkeley_semesters": semesters},
    }


def _row(annual=None):
    return {"annual_tuition": annual}


def test_tuition_compatible_missing_cost() -> None:
    assert _tuition_compatible(_prog(cost_usd=None, semesters=4), _row(annual=20000)) is True


def test_tuition_compatible_missing_freopp_annual() -> None:
    assert _tuition_compatible(_prog(cost_usd=80000, semesters=4), _row(annual=None)) is True


def test_tuition_compatible_missing_semesters() -> None:
    assert _tuition_compatible(_prog(cost_usd=80000, semesters=None), _row(annual=40000)) is True


def test_tuition_compatible_zero_freopp_annual() -> None:
    assert _tuition_compatible(_prog(cost_usd=80000, semesters=4), _row(annual=0)) is True


def test_tuition_compatible_exact_match() -> None:
    # 80000 / (4 * 0.5) = 40000 annual; ratio = 1.0 → compatible
    assert _tuition_compatible(_prog(cost_usd=80000, semesters=4), _row(annual=40000)) is True


def test_tuition_compatible_within_tolerance() -> None:
    # 80000 / 2 = 40000; freopp = 40500 → ratio ≈ 0.988 → compatible
    assert _tuition_compatible(_prog(cost_usd=80000, semesters=4), _row(annual=40500)) is True
    # freopp = 39500 → ratio ≈ 1.013 → compatible
    assert _tuition_compatible(_prog(cost_usd=80000, semesters=4), _row(annual=39500)) is True


def test_tuition_compatible_outside_tolerance() -> None:
    # 80000 / 2 = 40000; freopp = 50000 → ratio = 0.8 → incompatible
    assert _tuition_compatible(_prog(cost_usd=80000, semesters=4), _row(annual=50000)) is False
    # freopp = 30000 → ratio ≈ 1.33 → incompatible
    assert _tuition_compatible(_prog(cost_usd=80000, semesters=4), _row(annual=30000)) is False


def test_tuition_compatible_3_semester_program() -> None:
    # 60000 / (3 * 0.5) = 40000 annual; freopp = 40000 → compatible
    assert _tuition_compatible(_prog(cost_usd=60000, semesters=3), _row(annual=40000)) is True


# ── prioritize_candidates ───────────────────────────────────────────────────

def _make_row(cip_int, annual_tuition=40000):
    return {"program_cip_code": cip_int, "annual_tuition": annual_tuition}


def test_prioritize_exact_cip_first() -> None:
    rows = [_make_row(1101), _make_row(5004), _make_row(5001)]
    prog = _prog(semesters=4, cost_usd=80000)
    result = prioritize_candidates(rows, "50.0401", prog)
    assert result[0]["program_cip_code"] == 5004   # exact match first


def test_prioritize_same_family_before_unrelated() -> None:
    rows = [_make_row(1101), _make_row(5009), _make_row(5004)]
    prog = _prog(semesters=4, cost_usd=80000)
    result = prioritize_candidates(rows, "50.0401", prog)
    cips = [r["program_cip_code"] for r in result]
    assert cips.index(5004) < cips.index(5009) < cips.index(1101)


def test_prioritize_tuition_gate_filters_incompatible() -> None:
    compatible = _make_row(5004, annual_tuition=40000)      # 80000/2 = 40000 ✓
    incompatible = _make_row(5009, annual_tuition=80000)    # ratio = 0.5 ✗
    rows = [incompatible, compatible]
    prog = _prog(semesters=4, cost_usd=80000)
    result = prioritize_candidates(rows, "50.0401", prog)
    assert all(r["program_cip_code"] != 5009 for r in result)
    assert any(r["program_cip_code"] == 5004 for r in result)


def test_prioritize_falls_back_when_all_tuition_incompatible() -> None:
    # All rows have incompatible tuition — fallback to full pool
    rows = [_make_row(5004, 99999), _make_row(5009, 88888)]
    prog = _prog(semesters=4, cost_usd=80000)
    result = prioritize_candidates(rows, "50.0401", prog)
    assert len(result) == 2   # fallback returns all


def test_prioritize_caps_at_max_candidates() -> None:
    rows = [_make_row(i, 40000) for i in range(50)]
    prog = _prog(semesters=4, cost_usd=80000)
    result = prioritize_candidates(rows, "50.0401", prog)
    assert len(result) <= 25
