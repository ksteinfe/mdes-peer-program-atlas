"""Playwright post-load wait helpers (budget math only; no browser)."""

from __future__ import annotations

import pytest

from peer_atlas_cli import research_playwright as rp


def test_post_load_budget_default_scales_with_nav_timeout() -> None:
    assert 5.0 <= rp._post_load_budget_seconds(10.0) <= 20.0
    assert rp._post_load_budget_seconds(100.0) == 20.0


def test_post_load_budget_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEER_ATLAS_PLAYWRIGHT_POST_LOAD_SECONDS", "7.5")
    assert rp._post_load_budget_seconds(30.0) == 7.5


def test_stable_interval_default() -> None:
    assert rp._stable_interval_seconds() == 0.2


def test_stable_interval_env_ms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEER_ATLAS_PLAYWRIGHT_STABLE_INTERVAL_MS", "350")
    assert abs(rp._stable_interval_seconds() - 0.35) < 1e-6
