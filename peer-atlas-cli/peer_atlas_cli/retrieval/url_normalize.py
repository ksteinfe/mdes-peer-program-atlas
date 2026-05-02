"""Normalize URLs for stable cache keys."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def normalize_url(url: str) -> str:
    """Return a canonical form: scheme + host + path + sorted query; no fragment."""
    raw = (url or "").strip()
    if not raw:
        return ""
    p = urlparse(raw)
    scheme = (p.scheme or "https").lower()
    netloc = (p.netloc or "").lower()
    if not netloc and p.path:
        # bare "example.com/foo"
        path_part = p.path
        if "/" in path_part:
            host, _, rest = path_part.partition("/")
            netloc = host.lower()
            path = "/" + rest
        else:
            netloc = path_part.lower()
            path = ""
    else:
        path = p.path or "/"
    # strip default ports
    netloc = re.sub(r":80$", "", netloc, flags=re.IGNORECASE)
    netloc = re.sub(r":443$", "", netloc, flags=re.IGNORECASE)
    if not path.startswith("/"):
        path = "/" + path
    # drop trailing slash except root
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    q_pairs = sorted(parse_qsl(p.query, keep_blank_values=True))
    query = urlencode(q_pairs) if q_pairs else ""
    return urlunparse((scheme, netloc, path, "", query, ""))


def cache_key_for_url(url: str) -> str:
    n = normalize_url(url)
    return hashlib.sha256(n.encode("utf-8")).hexdigest() if n else ""


_WIN_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def cache_filename_for_url(url: str, *, max_stem: int = 96) -> str:
    """
    Human-readable cache filename stem + short hash suffix (collision-safe).
    Example: design.berkeley.edu___a1b2c3d4e5.json
    """
    n = normalize_url(url)
    digest = (cache_key_for_url(url)[:10]) if n else "empty"
    if not n:
        return f"__no_url__{digest}.json"
    p = urlparse(n)
    host = _WIN_BAD.sub("_", (p.netloc or "host").replace(":", "_"))
    path = _WIN_BAD.sub("_", (p.path or "").strip("/").replace("/", "_"))[:60]
    q = p.query
    qslug = ""
    if q:
        qslug = "_" + _WIN_BAD.sub("_", q)[:28]
    stem = f"{host}_{path}{qslug}".strip("_") or host
    stem = stem[:max_stem].rstrip("._")
    return f"{stem}__{digest}.json"
