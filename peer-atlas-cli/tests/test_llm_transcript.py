"""llm_transcript — per-invocation log under .peer-atlas/llm-last-session/."""

from __future__ import annotations

from pathlib import Path

import pytest

from peer_atlas_cli import llm_transcript as lt


@pytest.fixture(autouse=True)
def reset_transcript_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lt, "_REPO_ROOT", None)
    monkeypatch.setattr(lt, "_SEQ", 0)


def test_begin_clears_and_creates_session(tmp_path: Path) -> None:
    d = lt.session_dir(tmp_path)
    d.mkdir(parents=True)
    (d / "stale.txt").write_text("old", encoding="utf-8")
    lt.begin_cli_llm_session(tmp_path, argv=["peer-atlas", "validate"])
    assert (d / "_session.json").is_file()
    assert not (d / "stale.txt").exists()
    data = (d / "_session.json").read_text(encoding="utf-8")
    assert "peer-atlas" in data


def test_record_writes_request_and_response(tmp_path: Path) -> None:
    lt.begin_cli_llm_session(tmp_path, argv=[])
    lt.record_llm_exchange(system="S", user="U", response="R", step_slug="node-positioning")
    d = lt.session_dir(tmp_path)
    assert (d / "00001--node-positioning-request.txt").read_text(encoding="utf-8").endswith(
        "=== user ===\nU\n"
    )
    assert (d / "00001--node-positioning-response.txt").read_text(encoding="utf-8") == "R"


def test_record_default_slug_exchange(tmp_path: Path) -> None:
    lt.begin_cli_llm_session(tmp_path, argv=[])
    lt.record_llm_exchange(system="a", user="b", response="c")
    d = lt.session_dir(tmp_path)
    assert (d / "00001--exchange-request.txt").is_file()


def test_sanitize_transcript_slug() -> None:
    assert lt.sanitize_transcript_slug("Foo Bar!!!") == "foo-bar"


def test_record_noop_without_begin(tmp_path: Path) -> None:
    lt.record_llm_exchange(system="a", user="b", response="c")
    assert not lt.session_dir(tmp_path).exists()
