"""Fetch URL text for research flows."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

import httpx

from peer_atlas_cli.fetch_limits import coalesce_per_url_limit

# Many .edu sites block non-browser User-Agents or minimal clients. Use a common
# desktop Chrome fingerprint; httpx still decompresses gzip/br per Accept-Encoding.
_DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


def _headers_for_url(url: str) -> dict[str, str]:
    """Build browser-like headers. Optional `PEER_ATLAS_FETCH_COOKIE` env for gated pages."""
    h = dict(_DEFAULT_HEADERS)
    try:
        p = urlparse(url)
        if p.scheme and p.netloc:
            origin = f"{p.scheme}://{p.netloc}/"
            h["Referer"] = origin
            h["Sec-Fetch-Site"] = "same-origin"
        else:
            h["Sec-Fetch-Site"] = "none"
    except Exception:
        h["Sec-Fetch-Site"] = "none"
    cookie = os.environ.get("PEER_ATLAS_FETCH_COOKIE", "").strip()
    if cookie:
        h["Cookie"] = cookie
    return h


def _headers_minimal(url: str) -> dict[str, str]:
    """Second-chance profile: no Referer; some CDNs behave differently."""
    h = {
        "User-Agent": _DEFAULT_HEADERS["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    cookie = os.environ.get("PEER_ATLAS_FETCH_COOKIE", "").strip()
    if cookie:
        h["Cookie"] = cookie
    return h


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


@dataclass
class FetchUrlResult:
    """Outcome of a best-effort HTTP GET (may be non-200 with placeholder body)."""

    text: str
    status_code: int | None
    notes: str


def _fetch_url_text_httpx_lenient(
    url: str, *, timeout: float = 30.0, max_chars: int = 120_000
) -> FetchUrlResult:
    """httpx-only fetch with retries (fallback when Playwright is unavailable or non-200)."""
    retries = _int_env("PEER_ATLAS_FETCH_RETRIES", 3)
    delay_ms = _int_env("PEER_ATLAS_FETCH_RETRY_DELAY_MS", 500)
    strategies: tuple[Callable[[str], dict[str, str]], ...] = (
        _headers_for_url,
        _headers_minimal,
    )
    last_status: int | None = None
    last_body = ""
    notes_parts: list[str] = []

    for attempt in range(retries):
        for strat in strategies:
            headers = strat(url)
            try:
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    r = client.get(url, headers=headers)
                last_status = r.status_code
                if r.status_code == 200:
                    text = r.text
                    lim = coalesce_per_url_limit(max_chars)
                    if len(text) > lim:
                        text = text[:lim] + "\n\n[truncated]"
                    note = "; ".join(notes_parts) if notes_parts else "OK"
                    return FetchUrlResult(text, 200, note)
                last_body = (r.text or "")[:2000]
                notes_parts.append(f"HTTP {r.status_code} ({strat.__name__})")
            except httpx.HTTPError as e:
                notes_parts.append(f"{type(e).__name__}: {e}")
                last_status = None
        if attempt + 1 < retries:
            time.sleep(delay_ms / 1000.0)

    sc = last_status or 0
    placeholder = (
        f"[Peer Atlas fetch: HTTP {sc or 'error'} — no HTML body available for this URL.]\n"
        f"Last response excerpt (if any):\n{last_body[:800]}"
    )
    note = (
        "Search snippet evidence; page fetch returned "
        f"{sc if sc else 'error'}"
        + (f" ({'; '.join(notes_parts[-3:])})" if notes_parts else "")
        + "."
    )
    lim_ph = coalesce_per_url_limit(max_chars)
    return FetchUrlResult(placeholder[:lim_ph], last_status, note)


def fetch_url_text_lenient(
    url: str, *, timeout: float = 30.0, max_chars: int = 120_000
) -> FetchUrlResult:
    """
    Fetch URL body: try Playwright Chromium first; on missing Playwright, errors, or
    non-200 response, fall back to httpx retries. Never raises for HTTP error status.
    """
    try:
        from peer_atlas_cli.research_playwright import fetch_url_text_playwright_chromium

        pw = fetch_url_text_playwright_chromium(url, timeout=timeout, max_chars=max_chars)
        if pw is not None and pw.status_code == 200:
            return pw
    except Exception:
        pass
    return _fetch_url_text_httpx_lenient(url, timeout=timeout, max_chars=max_chars)


def fetch_url_text(url: str, *, timeout: float = 30.0, max_chars: int = 120_000) -> str:
    """Strict fetch: raises after lenient retries if status is not 200."""
    res = fetch_url_text_lenient(url, timeout=timeout, max_chars=max_chars)
    if res.status_code != 200:
        raise RuntimeError(
            f"GET {url!r} failed (HTTP {res.status_code}): {res.notes}"
        )
    return res.text
