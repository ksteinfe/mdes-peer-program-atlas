"""clear-programs command — empty corpus programs list."""

from __future__ import annotations

import sys

import click

from peer_atlas_cli.corpus_io import clear_all_programs, load_corpus, programs_list
from peer_atlas_cli.repo_root import find_repo_root


@click.command("clear-programs")
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Do not prompt for confirmation.",
)
def clear_programs_cmd(yes: bool) -> None:
    """Remove every program from corpus/programs.json (keeps corpus_metadata)."""
    root = find_repo_root()
    data_path = root / "corpus" / "programs.json"
    if not data_path.is_file():
        click.echo(f"Missing corpus file: {data_path}", err=True)
        sys.exit(1)

    preview = load_corpus(root)
    n = len(programs_list(preview))
    if n == 0:
        click.echo("Corpus already has zero programs; nothing to do.")
        return

    if not yes:
        click.confirm(
            click.style(
                f"This will DELETE all {n} program(s) from corpus/programs.json "
                "(programs array becomes []). corpus_metadata is kept.",
                fg="yellow",
            ),
            abort=True,
        )

    removed, archive = clear_all_programs(root)
    if archive is not None:
        click.echo(f"Saved pre-clear copy:\n  {archive}")
    click.echo(
        f"Removed {removed} program(s). corpus/programs.json now has an empty programs array."
    )
