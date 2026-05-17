"""Unit tests for run_cip_code_step skip logic (no LLM required)."""

from __future__ import annotations

from unittest.mock import MagicMock

from peer_atlas_cli.llm_nodes import run_cip_code_step


def _prog(*, ipeds_unitid=None, cip_code=None) -> dict:
    return {
        "program_id": "test",
        "base_url": "https://example.edu/",
        "identity": {
            "institution_name": "Test U",
            "program_name": "Test MDes",
            "credential_name": "MDes",
            "degree_type": "MDes",
            "host_academic_units": ["Design"],
            "host_academic_model": "design_hosted",
            "location_label": "Test City, United States",
            "first_degree_granted_year": "unknown",
            "cip_code": cip_code,
            "ipeds_unitid": ipeds_unitid,
        },
        "positioning": {"positioning_summary": "A design program.", "positioning_tags": []},
        "curriculum": {"curriculum_summary": "Design curriculum."},
        "llm_rationales": [],
    }


# ── skip paths (no LLM call should be made) ────────────────────────────────

def test_skips_when_no_ipeds_unitid() -> None:
    client = MagicMock()
    prog = _prog(ipeds_unitid=None, cip_code="unknown")
    result = run_cip_code_step(client=client, program=prog, categories_json="{}")
    assert result == ""
    client.complete.assert_not_called()
    assert prog["identity"]["cip_code"] is None


def test_skips_when_ipeds_unitid_empty_string() -> None:
    client = MagicMock()
    prog = _prog(ipeds_unitid="", cip_code="unknown")
    result = run_cip_code_step(client=client, program=prog, categories_json="{}")
    assert result == ""
    client.complete.assert_not_called()
    assert prog["identity"]["cip_code"] is None


def test_skips_when_cip_already_valid() -> None:
    client = MagicMock()
    prog = _prog(ipeds_unitid="110635", cip_code="50.0401")
    result = run_cip_code_step(client=client, program=prog, categories_json="{}")
    assert result == ""
    client.complete.assert_not_called()
    # existing value preserved
    assert prog["identity"]["cip_code"] == "50.0401"


def test_skips_when_cip_already_valid_other_code() -> None:
    client = MagicMock()
    prog = _prog(ipeds_unitid="110635", cip_code="14.0101")
    result = run_cip_code_step(client=client, program=prog, categories_json="{}")
    assert result == ""
    client.complete.assert_not_called()


# ── LLM paths (should call client.complete) ────────────────────────────────

def _mock_client(cip_value):
    client = MagicMock()
    client.complete.return_value = (
        f'{{"cip_code": "{cip_value}", '
        '"rationale": {"feature": "identity.cip_code", "source_url": "", '
        '"note": "test", "llm_title": "CIP code classification", "retrieved_date": ""}}'
    )
    return client


def test_calls_llm_when_cip_is_unknown() -> None:
    client = _mock_client("50.0401")
    prog = _prog(ipeds_unitid="110635", cip_code="unknown")
    result = run_cip_code_step(client=client, program=prog, categories_json="{}")
    assert result != ""
    client.complete.assert_called_once()
    assert prog["identity"]["cip_code"] == "50.0401"


def test_calls_llm_when_cip_is_null() -> None:
    client = _mock_client("50.0401")
    prog = _prog(ipeds_unitid="110635", cip_code=None)
    result = run_cip_code_step(client=client, program=prog, categories_json="{}")
    assert result != ""
    client.complete.assert_called_once()


def test_calls_llm_when_cip_is_INVALID() -> None:
    client = _mock_client("unknown")
    prog = _prog(ipeds_unitid="110635", cip_code="INVALID")
    result = run_cip_code_step(client=client, program=prog, categories_json="{}")
    assert result != ""
    client.complete.assert_called_once()


def test_replaces_existing_cip_code_rationale() -> None:
    """Ensures exactly one identity.cip_code rationale row after the step."""
    client = _mock_client("50.0401")
    prog = _prog(ipeds_unitid="110635", cip_code="unknown")
    prog["llm_rationales"] = [
        {"feature": "identity.cip_code", "source_url": "", "note": "old",
         "llm_title": "old", "retrieved_date": ""},
        {"feature": "identity.cip_code", "source_url": "", "note": "also old",
         "llm_title": "old2", "retrieved_date": ""},
        {"feature": "identity.institution_name", "source_url": "https://x.edu",
         "note": "n", "llm_title": "t", "retrieved_date": ""},
    ]
    run_cip_code_step(client=client, program=prog, categories_json="{}")
    cip_rats = [r for r in prog["llm_rationales"] if r.get("feature") == "identity.cip_code"]
    assert len(cip_rats) == 1
    # other rationales preserved
    other_rats = [r for r in prog["llm_rationales"] if r.get("feature") != "identity.cip_code"]
    assert len(other_rats) == 1
