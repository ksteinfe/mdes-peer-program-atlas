"""Concise LLM failure reporting for the CLI."""

from __future__ import annotations

import json
import os
from typing import Any

import click

_DEFAULT_PREVIEW = 1_400
_MAX_ERROR_LINES = 28


def _llm_debug_enabled() -> bool:
    return os.environ.get("PEER_ATLAS_LLM_DEBUG", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def echo_validation_errors(
    errs: list[str],
    *,
    intro: str | None = None,
    max_lines: int = _MAX_ERROR_LINES,
) -> None:
    """Print a capped list of validation / schema lines to stderr."""
    if intro:
        click.echo(intro, err=True)
    n = len(errs)
    if n == 0:
        click.echo("(no validation lines)", err=True)
        return
    click.echo(f"Validation issues ({n}); showing first {min(max_lines, n)}:", err=True)
    for line in errs[:max_lines]:
        click.echo(f"  {line}", err=True)
    if n > max_lines:
        click.echo(f"  … and {n - max_lines} more. Set PEER_ATLAS_LLM_DEBUG=1 for full context.", err=True)


def echo_llm_raw_and_parsed(
    raw: str,
    parsed: dict[str, Any] | None,
    *,
    intro: str,
    schema_errors: list[str] | None = None,
    max_chars: int = _DEFAULT_PREVIEW,
) -> None:
    """
    Summarize an LLM failure. By default: short intro, optional schema lines, small raw
    preview. Set PEER_ATLAS_LLM_DEBUG=1 for full raw + parsed JSON dumps.
    """
    debug = _llm_debug_enabled()
    raw_len = len(raw) if raw else 0
    click.echo(f"{intro} (raw {raw_len} chars)", err=True)

    if schema_errors:
        echo_validation_errors(schema_errors, intro="")

    if not debug:
        if raw and raw.strip():
            preview = raw.strip()
            if len(preview) > max_chars:
                head = preview[: max_chars // 2]
                tail = preview[-(max_chars // 2) :]
                preview = f"{head}\n… [{len(preview) - len(head) - len(tail)} chars omitted] …\n{tail}"
            click.echo("--- Raw preview (set PEER_ATLAS_LLM_DEBUG=1 for full) ---", err=True)
            click.echo(preview, err=True)
        if parsed is not None:
            click.echo(
                "(Parsed object omitted; set PEER_ATLAS_LLM_DEBUG=1 to dump JSON.)",
                err=True,
            )
        return

    if raw:
        preview = raw.strip()
        if len(preview) > 24_000:
            preview = preview[:24_000] + "\n… [truncated raw]"
        click.echo("--- Raw LLM text ---", err=True)
        click.echo(preview, err=True)
    if parsed is not None:
        try:
            dumped = json.dumps(parsed, indent=2, ensure_ascii=False)
            if len(dumped) > 24_000:
                dumped = dumped[:24_000] + "\n… [truncated parsed]"
            click.echo("--- Parsed object ---", err=True)
            click.echo(dumped, err=True)
        except (TypeError, ValueError) as e:
            click.echo(f"(Could not serialize parsed object: {e})", err=True)
