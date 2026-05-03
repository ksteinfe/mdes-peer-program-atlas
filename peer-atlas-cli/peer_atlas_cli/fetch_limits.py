"""Per-URL fetch / cache character limits (avoid premature ``[truncated]`` on evidence-sized pages)."""

from __future__ import annotations

import os

# Callers below this many chars keep their exact limit (tight evidence / rationale fetches).
_SMALL_REQUEST_THRESHOLD = 50_000


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def fetch_char_ceiling() -> int:
    """Hard cap on any single stored or downloaded HTML string (characters)."""
    return _int_env("PEER_ATLAS_FETCH_MAX_CHARS", 33_554_432)  # 32 MiB


def fetch_evidence_floor_chars() -> int:
    """
    When ``requested_max`` is at least ``_SMALL_REQUEST_THRESHOLD``, the effective
    limit is at least this floor (so ``120_000`` becomes multi‑MiB, not 120 KiB).
    """
    return _int_env("PEER_ATLAS_FETCH_EVIDENCE_FLOOR_CHARS", 8_388_608)  # 8 MiB


def coalesce_per_url_limit(requested_max: int) -> int:
    """
    Resolve per-URL limit for raw download, Playwright snapshot, and simplified
    HTML written to the URL cache.

    - ``requested_max <= 0`` → use ``fetch_char_ceiling()`` only.
    - ``requested_max < 50_000`` → honor the caller (capped by ceiling).
    - Otherwise → ``min(ceiling, max(requested, evidence_floor))``.
    """
    ce = fetch_char_ceiling()
    if requested_max <= 0:
        return ce
    if requested_max < _SMALL_REQUEST_THRESHOLD:
        return min(ce, requested_max)
    fl = fetch_evidence_floor_chars()
    return min(ce, max(requested_max, fl))


def raw_download_cap(requested_max: int) -> int:
    """Bytes/characters to request from Playwright/httpx before HTML simplification."""
    lim = coalesce_per_url_limit(requested_max)
    ce = fetch_char_ceiling()
    # Raw HTML is usually larger than simplified output; allow extra headroom.
    return min(ce, max(lim, lim * 4))
