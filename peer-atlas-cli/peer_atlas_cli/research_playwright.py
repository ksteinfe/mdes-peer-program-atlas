"""Chromium (Playwright) fetch for research flows — primary path before httpx fallback."""

from __future__ import annotations

import atexit
import os
import threading
import time
from typing import Any

from peer_atlas_cli.html_text import CONTENT_REGION_SELECTORS


_pw_lock = threading.Lock()
_playwright = None
_browser = None
_context = None


def _close_playwright() -> None:
    global _playwright, _browser, _context
    with _pw_lock:
        ctx, br, pw = _context, _browser, _playwright
        _context = _browser = _playwright = None
    try:
        if ctx is not None:
            ctx.close()
    except Exception:
        pass
    try:
        if br is not None:
            br.close()
    except Exception:
        pass
    try:
        if pw is not None:
            pw.stop()
    except Exception:
        pass


atexit.register(_close_playwright)


def _playwright_context():
    """Lazy singleton BrowserContext (Chromium)."""
    global _playwright, _browser, _context
    with _pw_lock:
        if _context is not None:
            return _context
        from playwright.sync_api import sync_playwright

        headed = os.environ.get("PEER_ATLAS_PLAYWRIGHT_HEADED", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        pw = None
        br = None
        ctx = None
        try:
            pw = sync_playwright().start()
            br = pw.chromium.launch(headless=not headed)
            extra: dict = {}
            cookie = os.environ.get("PEER_ATLAS_FETCH_COOKIE", "").strip()
            if cookie:
                extra["extra_http_headers"] = {"Cookie": cookie}
            ctx = br.new_context(**extra)
            _playwright = pw
            _browser = br
            _context = ctx
            return _context
        except Exception:
            try:
                if ctx is not None:
                    ctx.close()
            except Exception:
                pass
            try:
                if br is not None:
                    br.close()
            except Exception:
                pass
            try:
                if pw is not None:
                    pw.stop()
            except Exception:
                pass
            raise


def _post_load_budget_seconds(nav_timeout: float) -> float:
    """
    Wall-clock budget after ``domcontentloaded`` for content-selector waits +
    text-stability polling (capped).
    """
    raw = os.environ.get("PEER_ATLAS_PLAYWRIGHT_POST_LOAD_SECONDS", "").strip()
    if raw:
        try:
            return max(0.0, min(float(raw), 120.0))
        except ValueError:
            pass
    return min(20.0, max(5.0, float(nav_timeout) * 0.45))


def _stable_interval_seconds() -> float:
    raw = os.environ.get("PEER_ATLAS_PLAYWRIGHT_STABLE_INTERVAL_MS", "").strip()
    if raw:
        try:
            ms = int(raw)
            return max(0.05, min(2.0, ms / 1000.0))
        except ValueError:
            pass
    return 0.2


def _wait_first_content_selector(
    page: Any, selectors: tuple[str, ...], *, deadline: float
) -> str | None:
    """Return the first selector that attaches before ``deadline``, or ``None``."""
    for sel in selectors:
        if time.monotonic() >= deadline:
            return None
        remaining_ms = int(max(250, min(8000, (deadline - time.monotonic()) * 1000)))
        try:
            page.wait_for_selector(sel, state="attached", timeout=remaining_ms)
            return sel
        except Exception:
            continue
    return None


def _region_inner_text_snippet(page: Any, region_selector: str | None) -> str:
    """Bounded inner text for stability comparison."""
    cap = 150_000
    if region_selector:
        loc = page.locator(region_selector).first
        if loc.count() == 0:
            return ""
        return str(loc.inner_text(timeout=3000))[:cap]
    body = page.locator("body")
    return str(body.inner_text(timeout=3000))[:cap]


def _wait_text_stable_pair(
    page: Any, region_selector: str | None, *, deadline: float
) -> None:
    """
    Poll until two consecutive inner-text samples match (separated by a short sleep),
    or ``deadline`` is reached.
    """
    interval = _stable_interval_seconds()
    while time.monotonic() + interval * 2 <= deadline:
        a = _region_inner_text_snippet(page, region_selector)
        time.sleep(interval)
        if time.monotonic() >= deadline:
            return
        b = _region_inner_text_snippet(page, region_selector)
        if a == b:
            return


def fetch_url_text_playwright_chromium(
    url: str, *, timeout: float
) -> "FetchUrlResult | None":
    """
    Navigate with headless Chromium; return FetchUrlResult on completion (any status),
    or None if Playwright is unavailable before navigation (e.g. ImportError).

    After ``domcontentloaded``, waits for the first matching **content-region**
    selector (same list as ``html_text.CONTENT_REGION_SELECTORS``), then runs a
    short **text-stability** pass (two matching inner-text samples of that region,
    or ``body`` if no region matched) before ``page.content()``.
    """
    from peer_atlas_cli.research import FetchUrlResult

    try:
        ctx = _playwright_context()
    except Exception:
        return None

    page = ctx.new_page()
    timeout_ms = max(1, int(timeout * 1000))
    status: int | None = None
    notes_parts: list[str] = ["playwright/chromium"]
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        if resp is not None:
            status = resp.status

        post_deadline = time.monotonic() + _post_load_budget_seconds(timeout)
        found = _wait_first_content_selector(
            page, CONTENT_REGION_SELECTORS, deadline=post_deadline
        )
        _wait_text_stable_pair(page, found, deadline=post_deadline)
        if found:
            notes_parts.append(f"content_wait={found!r}")

        if os.environ.get("PEER_ATLAS_PLAYWRIGHT_SCROLL_MAIN", "1").strip().lower() not in (
            "0",
            "false",
            "no",
        ):
            try:
                if found:
                    page.locator(found).first.scroll_into_view_if_needed(timeout=3000)
                page.evaluate(
                    "() => { window.scrollTo(0, document.body?.scrollHeight ?? 0); }"
                )
                time.sleep(0.15)
            except Exception:
                pass

        html = page.content()
        note = "; ".join(notes_parts)
        if status is not None and status != 200:
            note = f"{note}; HTTP {status}"
        return FetchUrlResult(html, status, note)
    except Exception as e:
        notes_parts.append(f"{type(e).__name__}: {e}")
        return FetchUrlResult(
            f"[Peer Atlas fetch: Playwright error — no HTML body available for this URL.]\n{e}",
            status,
            "; ".join(notes_parts),
        )
    finally:
        try:
            page.close()
        except Exception:
            pass
