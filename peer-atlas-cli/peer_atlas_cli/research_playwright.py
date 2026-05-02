"""Chromium (Playwright) fetch for research flows — primary path before httpx fallback."""

from __future__ import annotations

import atexit
import os
import threading


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


def fetch_url_text_playwright_chromium(
    url: str, *, timeout: float, max_chars: int
) -> "FetchUrlResult | None":
    """
    Navigate with headless Chromium; return FetchUrlResult on completion (any status),
    or None if Playwright is unavailable before navigation (e.g. ImportError).
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
        html = page.content()
        if len(html) > max_chars:
            html = html[:max_chars] + "\n\n[truncated]"
        note = "; ".join(notes_parts)
        if status is not None and status != 200:
            note = f"{note}; HTTP {status}"
        return FetchUrlResult(html, status, note)
    except Exception as e:
        notes_parts.append(f"{type(e).__name__}: {e}")
        return FetchUrlResult(
            (
                f"[Peer Atlas fetch: Playwright error — no HTML body available for this URL.]\n{e}"
            )[:max_chars],
            status,
            "; ".join(notes_parts),
        )
    finally:
        try:
            page.close()
        except Exception:
            pass
