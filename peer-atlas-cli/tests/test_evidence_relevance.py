"""evidence_relevance ranking and anchors."""

from __future__ import annotations

from peer_atlas_cli.retrieval.evidence_relevance import rank_hits_for_program


def test_urban_design_hit_dropped_when_strict_and_mdes_anchor() -> None:
    program = {
        "identity": {
            "credential_name": "MDes",
            "degree_type": "MDes",
            "program_name": "Master of Design",
        }
    }
    seed = "https://design.berkeley.edu/about-mdes-program-design"
    hits = [
        {
            "url": "https://ced.berkeley.edu/iurd/urban-design",
            "title": "Urban Design | IURD",
            "content": "Graduate urban design at CED.",
        },
        {
            "url": "https://design.berkeley.edu/mdes-program-design-2",
            "title": "MDes curriculum",
            "content": "Required courses for the Berkeley MDes.",
        },
    ]
    ranked = rank_hits_for_program(
        hits,
        program,
        seed_url=seed,
        user_query="Berkeley MDes",
        strict_anchor_filter=True,
    )
    urls = [h["url"] for h in ranked]
    assert len(urls) == 1
    assert "design.berkeley.edu" in urls[0]


def test_seed_host_passes_without_anchor_in_blob() -> None:
    program = {"identity": {}}
    seed = "https://design.berkeley.edu/foo"
    hits = [
        {
            "url": "https://design.berkeley.edu/foo",
            "title": "Home",
            "content": "Little text.",
        },
    ]
    ranked = rank_hits_for_program(
        hits,
        program,
        seed_url=seed,
        user_query="",
        strict_anchor_filter=True,
    )
    assert len(ranked) == 1
