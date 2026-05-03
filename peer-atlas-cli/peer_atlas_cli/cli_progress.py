"""Shared stderr formatting for long-running CLI commands (ingest, reconsider, etc.)."""

from __future__ import annotations

from urllib.parse import unquote, urlparse

import click

_CLI_RULE_WIDTH = 52


def cli_short_url(url: str, *, max_len: int = 64) -> str:
    """
    Host + path for stderr (no scheme/query/fragment). Strips leading ``www.`` from host.
    Long paths collapse to ``host/…/last-segment`` when over ``max_len``.
    """
    u = (url or "").strip()
    if not u:
        return ""
    try:
        p = urlparse(u)
    except ValueError:
        return u if len(u) <= max_len else u[: max_len - 1] + "…"
    host = (p.netloc or "").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    path = unquote((p.path or "").replace("//", "/")).rstrip("/")
    if not host:
        return u if len(u) <= max_len else u[: max_len - 1] + "…"
    base = host if not path else f"{host}{path}"
    if len(base) <= max_len:
        return base
    seg = path.rsplit("/", 1)[-1] if path else ""
    if seg and len(seg) <= max_len - 6:
        mid = f"{host}/…/{seg}"
        if len(mid) <= max_len:
            return mid
    return base[: max_len - 1] + "…"


def cli_rule_line(char: str = "=") -> None:
    click.echo(char * _CLI_RULE_WIDTH, err=True)


def cli_bracket_line(
    scope: str,
    task: str,
    message: str,
    *,
    indent_tabs: int = 0,
) -> None:
    """Print ``[scope|task] message`` with optional leading tabs."""
    tabs = "\t" * max(0, indent_tabs)
    click.echo(f"{tabs}[{scope}|{task}] {message}", err=True)
