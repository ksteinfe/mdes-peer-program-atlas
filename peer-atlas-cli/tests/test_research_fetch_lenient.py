"""fetch_url_text_lenient Playwright-first + httpx fallback."""

from __future__ import annotations

from unittest.mock import patch

from peer_atlas_cli import research


def test_lenient_returns_playwright_when_200() -> None:
    pw_ok = research.FetchUrlResult("<html>ok</html>", 200, "playwright/chromium")
    with patch(
        "peer_atlas_cli.research_playwright.fetch_url_text_playwright_chromium",
        return_value=pw_ok,
    ):
        with patch.object(research, "_fetch_url_text_httpx_lenient") as httpx_fn:
            r = research.fetch_url_text_lenient(
                "https://example.com/", timeout=1.0, max_chars=10_000
            )
    assert r is pw_ok
    httpx_fn.assert_not_called()


def test_lenient_falls_back_httpx_when_playwright_non_200() -> None:
    pw_403 = research.FetchUrlResult("forbidden", 403, "playwright/chromium; HTTP 403")
    httpx_ok = research.FetchUrlResult("<html>fallback</html>", 200, "OK")
    with patch(
        "peer_atlas_cli.research_playwright.fetch_url_text_playwright_chromium",
        return_value=pw_403,
    ):
        with patch.object(
            research, "_fetch_url_text_httpx_lenient", return_value=httpx_ok
        ) as httpx_fn:
            r = research.fetch_url_text_lenient(
                "https://example.com/", timeout=1.0, max_chars=10_000
            )
    assert r is httpx_ok
    httpx_fn.assert_called_once()


def test_lenient_falls_back_httpx_when_playwright_none() -> None:
    httpx_ok = research.FetchUrlResult("<html>fallback</html>", 200, "OK")
    with patch(
        "peer_atlas_cli.research_playwright.fetch_url_text_playwright_chromium",
        return_value=None,
    ):
        with patch.object(
            research, "_fetch_url_text_httpx_lenient", return_value=httpx_ok
        ) as httpx_fn:
            r = research.fetch_url_text_lenient(
                "https://example.com/", timeout=1.0, max_chars=10_000
            )
    assert r is httpx_ok
    httpx_fn.assert_called_once()
