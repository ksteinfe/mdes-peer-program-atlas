"""evidence_bundle helpers."""

from __future__ import annotations

from peer_atlas_cli.retrieval import evidence_bundle as eb
from peer_atlas_cli.retrieval.evidence_gathering_pipeline import is_non_web_document_url


def test_mash_curriculum_source_summaries_joins_sources() -> None:
    s = eb.mash_curriculum_source_summaries(
        [
            ("https://a.edu/req", "Core: INFO 202."),
            ("https://a.edu/paths", ""),
        ]
    )
    assert "### Source: https://a.edu/req" in s
    assert "INFO 202" in s
    assert "paths" not in s  # empty body skipped


def test_priority_curriculum_evidence_urls_degree_requirements_first() -> None:
    urls = [
        "https://www.ischool.berkeley.edu/programs/mims",
        "https://www.ischool.berkeley.edu/programs/mims/projects/2026",
        "https://www.ischool.berkeley.edu/programs/mims/degreerequirements",
        "https://www.ischool.berkeley.edu/programs/mims/paths",
    ]
    ordered = eb._priority_curriculum_evidence_urls(urls)
    assert ordered[0].endswith("/degreerequirements")
    assert "/projects/" in ordered[-1]


def test_is_non_web_document_url_detects_pdf() -> None:
    assert is_non_web_document_url("https://x.edu/a.pdf") is True
    assert is_non_web_document_url("https://x.edu/page") is False


def test_bundle_budget_unlimited() -> None:
    assert eb._bundle_budget_unlimited(0) is True
    assert eb._bundle_budget_unlimited(-1) is True
    assert eb._bundle_budget_unlimited(100) is False
