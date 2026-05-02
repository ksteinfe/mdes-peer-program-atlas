"""Pytest configuration: run CLI tests from repository root."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def _chdir_repo_root() -> None:
    prev = os.getcwd()
    os.chdir(REPO_ROOT)
    yield
    os.chdir(prev)
