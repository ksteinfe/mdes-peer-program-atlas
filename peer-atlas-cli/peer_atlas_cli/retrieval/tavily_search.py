"""Tavily web search API (https://docs.tavily.com)."""

from __future__ import annotations

import os
from typing import Any

import httpx

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


def tavily_api_key() -> str:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "TAVILY_API_KEY is not set; it is required for search-backed ingest steps."
        )
    return key


def search_urls(
    query: str,
    *,
    max_results: int = 5,
    timeout: float = 30.0,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Return Tavily results: each dict has url, title, content (snippet), optional score.
    """
    payload: dict[str, Any] = {
        "api_key": tavily_api_key(),
        "query": query.strip(),
        "max_results": max(1, min(max_results, 20)),
        "search_depth": "basic",
        "include_answer": False,
    }
    if include_domains:
        payload["include_domains"] = [d.strip() for d in include_domains if d and str(d).strip()]
    if exclude_domains:
        payload["exclude_domains"] = [d.strip() for d in exclude_domains if d and str(d).strip()]
    with httpx.Client(timeout=timeout) as client:
        r = client.post(TAVILY_SEARCH_URL, json=payload)
        r.raise_for_status()
        data = r.json()
    results = data.get("results")
    if not isinstance(results, list):
        return []
    out: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not url or not isinstance(url, str):
            continue
        out.append(
            {
                "url": url.strip(),
                "title": str(item.get("title") or ""),
                "content": str(item.get("content") or ""),
            }
        )
    return out
