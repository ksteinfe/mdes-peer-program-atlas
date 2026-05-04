"""remove-last-program command (tmp corpus)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from peer_atlas_cli.main import main


def _write_corpus(root: Path, programs: list) -> None:
    d = root / "corpus"
    d.mkdir(parents=True)
    schemas = root / "schemas"
    schemas.mkdir(parents=True)
    # Minimal schema files so find_repo_root + validate work if invoked
    for name in ("program.schema.json", "program_draft.schema.json"):
        src = Path(__file__).resolve().parents[2] / "schemas" / name
        if src.is_file():
            (schemas / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    cat = root / "categories_and_rules"
    cat.mkdir(parents=True)
    for fn in (
        "host_academic_models.json",
        "positioning_tags.json",
        "duration_categories.json",
        "unit_systems.json",
        "sequencedness.json",
        "verification_statuses.json",
        "course_types.json",
    ):
        src = Path(__file__).resolve().parents[2] / "categories_and_rules" / fn
        if src.is_file():
            (cat / fn).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    (d / "programs.json").write_text(
        json.dumps({"corpus_metadata": {"version": 1, "description": "t"}, "programs": programs}),
        encoding="utf-8",
    )


def _minimal_prog(pid: str, *, da: str | None = None, du: str | None = None) -> dict:
    base = {
        "program_id": pid,
        "base_url": f"https://{pid}.example.edu/",
        "sources": [],
        "llm_rationales": [
            {
                "feature": "x",
                "source_url": "https://x.edu/",
                "note": "",
                "llm_title": "x",
                "retrieved_date": "",
            }
        ],
        "identity": {
            "institution_name": "U",
            "program_name": "P",
            "credential_name": "M",
            "degree_type": "master's",
            "host_academic_units": ["D"],
            "host_academic_model": "design_hosted",
            "location_label": "US",
        },
        "positioning": {"positioning_summary": "", "positioning_tags": ["professional"]},
        "duration": {
            "length_in_berkeley_semesters": None,
            "duration_category": "variable_or_custom",
        },
        "degree_cost": {
            "base_currency": "USD",
            "exchange_rate_to_usd": None,
            "comparison_cost_usd": None,
            "cost_base_currency": None,
        },
        "curriculum": {
            "unit_system": "semester_credit_hours",
            "sequencedness": "flexible",
            "curriculum_summary": "",
            "offers_specialization": False,
            "core_courses": [],
            "electives": {"summary": "", "estimated_elective_course_count": None},
        },
        "verification": {
            "status": "llm_extracted",
            "verified_by": "",
            "verified_date": "",
        },
    }
    if da is not None:
        base["date_added"] = da
    if du is not None:
        base["date_updated"] = du
    return base


@pytest.fixture
def tiny_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Repo root with corpus + schemas + categories (minimal copy from workspace)."""
    root = tmp_path / "repo"
    root.mkdir()
    _write_corpus(
        root,
        [
            _minimal_prog("old_p", da="2026-01-01T00:00:00Z", du="2026-01-01T00:00:00Z"),
            _minimal_prog("new_p", da="2026-06-01T00:00:00Z", du="2026-06-01T00:00:00Z"),
        ],
    )
    monkeypatch.chdir(root)
    return root


def test_remove_last_program_removes_newest_by_date_added(tiny_repo: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["remove-last-program", "-y"])
    assert result.exit_code == 0, result.output
    data = json.loads((tiny_repo / "corpus" / "programs.json").read_text(encoding="utf-8"))
    assert len(data["programs"]) == 1
    assert data["programs"][0]["program_id"] == "old_p"


def test_remove_last_program_tie_breaks_to_later_row_when_same_date_added(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _write_corpus(
        root,
        [
            _minimal_prog("first", da="2026-01-01T00:00:00Z", du="2026-01-01T00:00:00Z"),
            _minimal_prog("second", da="2026-01-01T00:00:00Z", du="2026-01-01T00:00:00Z"),
        ],
    )
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(main, ["remove-last-program", "-y"])
    assert result.exit_code == 0, result.output
    data = json.loads((root / "corpus" / "programs.json").read_text(encoding="utf-8"))
    assert len(data["programs"]) == 1
    assert data["programs"][0]["program_id"] == "first"
