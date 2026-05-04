"""remove-last-program — drop the most recently added corpus row."""

from __future__ import annotations

import shutil
import sys

import click

from peer_atlas_cli.corpus_io import (
    corpus_path,
    dated_corpus_archive_path,
    load_corpus,
    programs_list,
    write_corpus,
)
from peer_atlas_cli.program_dates import index_most_recently_added_program
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import validate_corpus


@click.command("remove-last-program")
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Do not prompt for confirmation.",
)
def remove_last_program_cmd(yes: bool) -> None:
    """Remove the program most recently added to the corpus.

    Chooses the row with the greatest ``date_added`` (ISO strings; ties favor a
    later array index). If no program has ``date_added``, removes the last
    program in the ``programs`` array.
    """
    root = find_repo_root()
    path = corpus_path(root)
    if not path.is_file():
        click.echo(f"Missing corpus file: {path}", err=True)
        sys.exit(1)

    corpus = load_corpus(root)
    plist = programs_list(corpus)
    if not plist:
        click.echo("Corpus has no programs; nothing to remove.")
        return

    idx = index_most_recently_added_program(plist)
    if idx is None:
        click.echo("Corpus has no programs; nothing to remove.")
        return

    victim = plist[idx]
    pid = victim.get("program_id", "?")
    base_u = victim.get("base_url", "")

    if not yes:
        click.confirm(
            click.style(
                f"This will archive the current corpus file, then remove one program:\n"
                f"  program_id={pid!r}\n"
                f"  base_url={base_u!r}\n"
                f"(chosen index {idx} in programs[]).",
                fg="yellow",
            ),
            abort=True,
        )

    archive = dated_corpus_archive_path(root)
    shutil.copy2(path, archive)
    plist.pop(idx)

    enum_notes: list[str] = []
    errs = validate_corpus(
        root,
        corpus,
        category_repair_notes=enum_notes,
        repair_invalid_enums=True,
    )
    for line in enum_notes:
        click.echo(line, err=True)
    if errs:
        for e in errs:
            click.echo(e, err=True)
        click.echo("Refusing to write: corpus would be invalid after removal.", err=True)
        sys.exit(1)

    write_corpus(root, corpus)
    click.echo(f"Archived pre-change corpus to:\n  {archive}")
    click.echo(f"Removed program {pid!r} (index was {idx}).")
