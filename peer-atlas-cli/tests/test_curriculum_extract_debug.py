"""curriculum per-source extract stderr debug helper."""

from __future__ import annotations

import pytest

from peer_atlas_cli.llm_nodes import (
    curriculum_source_extract_debug_full_user_message,
    emit_curriculum_source_extract_llm_io,
)


def test_curriculum_source_extract_debug_full_user_message_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PEER_ATLAS_CURRICULUM_EXTRACT_DEBUG", raising=False)
    assert curriculum_source_extract_debug_full_user_message() is False
    monkeypatch.setenv("PEER_ATLAS_CURRICULUM_EXTRACT_DEBUG", "1")
    assert curriculum_source_extract_debug_full_user_message() is True


def test_emit_truncates_long_user_message_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PEER_ATLAS_CURRICULUM_EXTRACT_DEBUG", raising=False)
    buf: list[str] = []

    def emit(s: str) -> None:
        buf.append(s)

    user = "U" * 15_000
    emit_curriculum_source_extract_llm_io(
        emit,
        source_url="https://example.edu/curriculum",
        user_message=user,
        response="ASSISTANT_OUT",
    )
    joined = "\n".join(buf)
    assert "ASSISTANT_OUT" in joined
    assert "chars omitted" in joined
    assert user[:12_000] in joined


def test_emit_full_user_when_debug_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEER_ATLAS_CURRICULUM_EXTRACT_DEBUG", "1")
    buf: list[str] = []

    def emit(s: str) -> None:
        buf.append(s)

    user = "V" * 500
    emit_curriculum_source_extract_llm_io(
        emit,
        source_url="https://example.edu/a",
        user_message=user,
        response="R",
    )
    joined = "\n".join(buf)
    assert joined.count("V") == 500
    assert "R" in joined
