"""Resolve university-wide domain from program URLs (e.g. ischool.berkeley.edu → berkeley.edu)."""

from __future__ import annotations

from urllib.parse import urlparse

import tldextract


def registered_domain_for_url(url: str) -> str | None:
    """
    Return the registrable domain (eTLD+1) for scope-limited search, e.g.
    ``https://www.ischool.berkeley.edu/programs/mims`` → ``berkeley.edu``.
    """
    u = (url or "").strip()
    if not u:
        return None
    try:
        ext = tldextract.extract(u)
    except Exception:
        return None
    if not ext.domain or not ext.suffix:
        return None
    return f"{ext.domain}.{ext.suffix}".lower()


def hostname_matches_registered_domain(hostname: str, registered_domain: str) -> bool:
    h = (hostname or "").lower().strip()
    r = (registered_domain or "").lower().strip()
    if not h or not r:
        return False
    if h == r:
        return True
    return h.endswith("." + r)


def url_matches_registered_domain(url: str, registered_domain: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").strip()
    except ValueError:
        return False
    return hostname_matches_registered_domain(host, registered_domain)


def filter_hits_to_registered_domain(
    hits: list[dict], registered_domain: str
) -> list[dict]:
    out: list[dict] = []
    for h in hits:
        if not isinstance(h, dict):
            continue
        u = h.get("url")
        if isinstance(u, str) and url_matches_registered_domain(u, registered_domain):
            out.append(h)
    return out
