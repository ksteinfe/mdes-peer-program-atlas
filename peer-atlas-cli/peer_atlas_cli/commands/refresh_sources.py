"""refresh-sources — rebuild program ``sources`` from url-cache."""

from __future__ import annotations

import click

from peer_atlas_cli.corpus_io import load_corpus, write_corpus
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import validate_corpus
from peer_atlas_cli.sources_from_url_cache import rebuild_all_program_sources


@click.command("refresh-sources")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate only; do not write corpus/programs.json.",
)
def refresh_sources_cmd(dry_run: bool) -> None:
    """
    Set each program's top-level ``sources`` to the sorted unique list of ``url``
    values from url-cache JSON files whose registrable domain matches the program's
    ``base_url`` (same rule as host-scoped search).
    """
    root = find_repo_root()
    corpus = load_corpus(root)
    rebuild_all_program_sources(corpus, root)
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
        for e in errs[:80]:
            click.echo(e, err=True)
        raise click.ClickException("corpus invalid after rebuild (see errors above).")
    for p in corpus.get("programs") or []:
        if isinstance(p, dict):
            pid = str(p.get("program_id") or "?")
            n = len(p.get("sources") or [])
            click.echo(f"{pid}: {n} sources")
    if dry_run:
        click.echo("Dry run: not writing corpus.")
        return
    write_corpus(root, corpus)
    click.echo("Wrote corpus/programs.json")
