"""validate command."""

from __future__ import annotations

import json
import pathlib
import sys

import click

from peer_atlas_cli.corpus_io import corpus_path
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import validate_corpus


@click.command("validate")
@click.option(
    "--corpus",
    "corpus_file",
    type=click.Path(path_type=pathlib.Path, exists=True),
    default=None,
    help="Override corpus JSON path (default: corpus/programs.json under repo root).",
)
def validate_cmd(corpus_file: pathlib.Path | None) -> None:
    """Validate corpus against JSON Schema and category files."""
    root = find_repo_root()
    path = corpus_file or corpus_path(root)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    errors = validate_corpus(root, data)
    if errors:
        for e in errors:
            click.echo(e, err=True)
        sys.exit(1)
    click.echo("OK: corpus validates.")
