"""Shared stderr formatting for long-running CLI commands (ingest, reconsider, etc.)."""

from __future__ import annotations

import click

_CLI_RULE_WIDTH = 72


def cli_rule_line(char: str = "=") -> None:
    click.echo(char * _CLI_RULE_WIDTH, err=True)


def cli_bracket_line(
    scope: str,
    task: str,
    message: str,
    *,
    indent_tabs: int = 0,
) -> None:
    """Print ``[scope (task)] message`` with optional leading tabs."""
    tabs = "\t" * max(0, indent_tabs)
    click.echo(f"{tabs}[{scope} ({task})] {message}", err=True)
