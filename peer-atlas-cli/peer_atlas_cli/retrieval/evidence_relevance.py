"""Rank and filter Tavily hits so evidence matches the program being ingested."""

from __future__ import annotations

import re
from typing import Any, Sequence
from urllib.parse import urlparse

from peer_atlas_cli.retrieval.url_normalize import normalize_url

# Single words that match many unrelated pages on the same university domain.
_TOKEN_STOP = frozenset(
    {
        "about",
        "and",
        "berkeley",
        "college",
        "course",
        "courses",
        "degree",
        "design",
        "education",
        "from",
        "graduate",
        "host",
        "master",
        "program",
        "school",
        "the",
        "unknown",
        "university",
        "with",
    }
)


def _hostname(url: str) -> str:
    try:
        h = (urlparse((url or "").strip()).hostname or "").lower()
    except ValueError:
        return ""
    return h.removeprefix("www.")


def _registrable_domain(host: str) -> str | None:
    """
    Naive registrable domain (good enough for *.edu / most corporate hosts).
    """
    if not host:
        return None
    parts = host.split(".")
    if len(parts) < 2:
        return None
    if len(parts) >= 3 and parts[-2] == "ac" and parts[-1] == "uk":
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _hit_blob(hit: dict) -> str:
    u = str(hit.get("url") or "")
    t = str(hit.get("title") or "")
    c = str(hit.get("content") or "")
    return f"{u} {t} {c}".lower()


def strong_anchor_phrases(
    program: dict,
    *,
    seed_url: str,
    user_query: str,
    extra: Sequence[str] | None = None,
) -> list[str]:
    """
    Short substrings that should appear on on-target pages.
    Excludes generic tokens so \"design\" alone does not match every studio page.
    """
    ident = program.get("identity") if isinstance(program.get("identity"), dict) else {}
    out: list[str] = []
    seen: set[str] = set()

    def add(phrase: str) -> None:
        p = phrase.strip().lower()
        if len(p) < 3 or p in seen:
            return
        seen.add(p)
        out.append(p)

    for key in ("credential_name", "degree_type", "program_name"):
        raw = ident.get(key)
        if isinstance(raw, str) and raw.strip():
            add(raw.strip())

    path = (urlparse(seed_url).path or "").lower()
    for m in re.finditer(r"[a-z0-9]{4,}", path.replace("-", " ").replace("_", " ")):
        tok = m.group(0)
        if tok not in _TOKEN_STOP:
            add(tok)
    if "mdes" in path or "m-des" in path:
        add("mdes")

    q = (user_query or "").strip().lower()
    if q:
        for m in re.finditer(r"[a-z0-9]{3,}", q):
            tok = m.group(0)
            if tok in _TOKEN_STOP:
                continue
            add(tok)

    if extra:
        for x in extra:
            if isinstance(x, str) and x.strip():
                add(x.strip())
    return out


def hit_matches_program_anchors(
    hit: dict,
    anchors: list[str],
    *,
    seed_url: str,
) -> bool:
    """False only when we have anchors and this hit matches none (and is not the seed host)."""
    if not anchors:
        return True
    blob = _hit_blob(hit)
    seed_h = _hostname(seed_url)
    hit_h = _hostname(str(hit.get("url") or ""))
    if seed_h and hit_h == seed_h:
        return True
    return any(a in blob for a in anchors)


def relevance_score(
    hit: dict,
    anchors: list[str],
    *,
    seed_url: str,
) -> float:
    """Higher = more likely the right program; used to sort before fetching."""
    score = 0.0
    blob = _hit_blob(hit)
    seed_h = _hostname(seed_url)
    hit_h = _hostname(str(hit.get("url") or ""))
    if seed_h and hit_h == seed_h:
        score += 200.0
    elif seed_h and hit_h:
        sd = _registrable_domain(seed_h)
        hd = _registrable_domain(hit_h)
        if sd and hd and sd == hd:
            score += 25.0
    for a in anchors:
        if a in blob:
            score += 12.0 + min(30.0, float(len(a)))
    return score


def dedupe_hits_preserve_order(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for h in hits:
        if not isinstance(h, dict):
            continue
        u = str(h.get("url") or "").strip()
        if not u:
            continue
        key = normalize_url(u)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def rank_hits_for_program(
    hits: list[dict[str, Any]],
    program: dict[str, Any],
    *,
    seed_url: str,
    user_query: str,
    strict_anchor_filter: bool,
    extra_anchor_phrases: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Deduplicate by URL, optionally drop anchor misses, then sort by relevance_score
    (seed host first, then anchor overlap).
    """
    uniq = dedupe_hits_preserve_order(hits)
    anchors = strong_anchor_phrases(
        program,
        seed_url=seed_url,
        user_query=user_query,
        extra=extra_anchor_phrases,
    )
    if strict_anchor_filter and anchors:
        filtered = [
            h for h in uniq if hit_matches_program_anchors(h, anchors, seed_url=seed_url)
        ]
        if filtered:
            uniq = filtered
    scored = [(relevance_score(h, anchors, seed_url=seed_url), i, h) for i, h in enumerate(uniq)]
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [h for _, _, h in scored]
