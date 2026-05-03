"""host_scope: registrable domain from base_url."""

from __future__ import annotations

from peer_atlas_cli.retrieval.host_scope import (
    registered_domain_for_url,
    url_matches_registered_domain,
)


def test_registered_domain_berkeley_ischool() -> None:
    u = "https://www.ischool.berkeley.edu/programs/mims"
    assert registered_domain_for_url(u) == "berkeley.edu"


def test_url_matches_registered_domain_subdomain() -> None:
    assert url_matches_registered_domain(
        "https://www.ischool.berkeley.edu/foo", "berkeley.edu"
    )
    assert not url_matches_registered_domain("https://example.com/", "berkeley.edu")
