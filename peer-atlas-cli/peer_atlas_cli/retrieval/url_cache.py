"""Disk cache for fetched URL bodies with TTL."""

from __future__ import annotations

import json
import os
import pathlib
import time
from typing import Any

from peer_atlas_cli.retrieval.url_normalize import (
    cache_filename_for_url,
    cache_key_for_url,
    normalize_url,
)

_DEFAULT_TTL_SECONDS = 172800  # 48h


def cache_ttl_seconds() -> float:
    raw = os.environ.get("PEER_ATLAS_FETCH_CACHE_TTL_SECONDS", "").strip()
    if not raw:
        return float(_DEFAULT_TTL_SECONDS)
    try:
        return max(0.0, float(raw))
    except ValueError:
        return float(_DEFAULT_TTL_SECONDS)


def cache_dir_for_repo(repo_root: pathlib.Path) -> pathlib.Path:
    override = os.environ.get("PEER_ATLAS_FETCH_CACHE_DIR", "").strip()
    if override:
        return pathlib.Path(override).expanduser()
    return repo_root / ".peer-atlas" / "url-cache"


def _legacy_path(cache_dir: pathlib.Path, url: str) -> pathlib.Path:
    key = cache_key_for_url(url)
    return cache_dir / f"{key}.json"


def _primary_path(cache_dir: pathlib.Path, url: str) -> pathlib.Path:
    return cache_dir / cache_filename_for_url(url)


def _read_entry(path: pathlib.Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def clear_cache_entry_for_url(cache_dir: pathlib.Path, url: str) -> int:
    """Remove primary and legacy JSON cache files for ``url`` if present.

    Returns the number of files successfully removed (0, 1, or 2).
    """
    n = 0
    for path in (_primary_path(cache_dir, url), _legacy_path(cache_dir, url)):
        try:
            if path.is_file():
                path.unlink()
                n += 1
        except OSError:
            continue
    return n


def read_raw_cache_entry(cache_dir: pathlib.Path, url: str) -> dict[str, Any] | None:
    """Read cache JSON if the file exists (ignores TTL). Used to patch ``body_markdown``."""
    for path in (_primary_path(cache_dir, url), _legacy_path(cache_dir, url)):
        data = _read_entry(path)
        if isinstance(data, dict):
            return data
    return None


def read_cached_entry(cache_dir: pathlib.Path, url: str) -> dict[str, Any] | None:
    """Return full cache entry dict if present and not expired; otherwise None."""
    ttl = cache_ttl_seconds()
    if ttl <= 0:
        return None
    for path in (_primary_path(cache_dir, url), _legacy_path(cache_dir, url)):
        data = _read_entry(path)
        if not isinstance(data, dict):
            continue
        fetched = float(data.get("fetched_at", 0))
        if time.time() - fetched > ttl:
            continue
        body = data.get("body")
        if isinstance(body, str):
            return data
    return None


def read_cached_body(cache_dir: pathlib.Path, url: str) -> str | None:
    """Return cached body if present and not expired; otherwise None."""
    entry = read_cached_entry(cache_dir, url)
    if entry is None:
        return None
    body = entry.get("body")
    return body if isinstance(body, str) else None


def write_cached_body(
    cache_dir: pathlib.Path,
    url: str,
    body: str,
    *,
    http_status: int | None = None,
    notes: str = "",
    body_markdown: str | None = None,
) -> pathlib.Path:
    """Write pretty-printed JSON cache entry; returns path written."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    norm = normalize_url(url)
    path = _primary_path(cache_dir, url)
    payload: dict[str, Any] = {
        "url": norm,
        "fetched_at": time.time(),
        "http_status": http_status,
        "notes": notes or "",
        "body": body,
    }
    if body_markdown is not None and body_markdown.strip():
        from peer_atlas_cli.retrieval.llm_evidence_markdown import sanitize_llm_text_for_json_storage

        payload["body_markdown"] = sanitize_llm_text_for_json_storage(body_markdown)
    payload["body_chars"] = len(body) if isinstance(body, str) else 0
    md = payload.get("body_markdown")
    payload["body_markdown_chars"] = len(md) if isinstance(md, str) else 0
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def patch_cached_body_markdown(cache_dir: pathlib.Path, url: str, body_markdown: str) -> None:
    """Merge ``body_markdown`` into an existing cache file (same ``fetched_at`` / ``body``)."""
    from peer_atlas_cli.retrieval.llm_evidence_markdown import sanitize_llm_text_for_json_storage

    data = read_raw_cache_entry(cache_dir, url)
    if not isinstance(data, dict):
        return
    if not isinstance(data.get("body"), str):
        return
    data["body_markdown"] = sanitize_llm_text_for_json_storage(body_markdown)
    body = data.get("body")
    data["body_chars"] = len(body) if isinstance(body, str) else 0
    md = data.get("body_markdown")
    data["body_markdown_chars"] = len(md) if isinstance(md, str) else 0
    path = _primary_path(cache_dir, url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
