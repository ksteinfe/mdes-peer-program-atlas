"""Retrieval: search, cache, evidence."""

from peer_atlas_cli.retrieval.evidence_bundle import (
    gather_evidence_for_node,
    gather_evidence_for_queries,
)
from peer_atlas_cli.retrieval.fetch_cached import fetch_url_text_cached
from peer_atlas_cli.retrieval.query_builders import (
    INGEST_NODE_ORDER,
    queries_for_core_course,
    queries_for_node,
)
from peer_atlas_cli.retrieval.tavily_search import search_urls, tavily_api_key
from peer_atlas_cli.retrieval.url_cache import cache_dir_for_repo, cache_ttl_seconds
from peer_atlas_cli.retrieval.url_normalize import cache_key_for_url, normalize_url

__all__ = [
    "INGEST_NODE_ORDER",
    "cache_dir_for_repo",
    "cache_key_for_url",
    "cache_ttl_seconds",
    "fetch_url_text_cached",
    "gather_evidence_for_node",
    "gather_evidence_for_queries",
    "normalize_url",
    "queries_for_core_course",
    "queries_for_node",
    "search_urls",
    "tavily_api_key",
]
