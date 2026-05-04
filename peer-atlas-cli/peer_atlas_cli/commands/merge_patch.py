"""merge-patch command."""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import click

from peer_atlas_cli.corpus_io import load_corpus, program_by_id, write_corpus
from peer_atlas_cli.program_dates import bump_date_updated
from peer_atlas_cli.json_paths import get_path, path_exists, set_path_flexible
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import validate_corpus, validate_patch_shape


def _deep_equal(a: object, b: object) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def apply_merge_patch_to_corpus(
    corpus: dict[str, Any],
    patch: dict[str, Any],
    *,
    repo_root: pathlib.Path,
    allow_new_paths: bool,
    skip_old_check: bool,
) -> list[tuple[str, str]]:
    programs = corpus.get("programs")
    if not isinstance(programs, list):
        raise ValueError("corpus.programs must be an array")

    applied: list[tuple[str, str]] = []
    for ch in patch.get("changes", []):
        pid = ch["program_id"]
        path = ch["path"]
        old_value = ch.get("old_value")
        new_value = ch["new_value"]
        prog = program_by_id(corpus, pid)
        if prog is None:
            raise ValueError(f"Unknown program_id: {pid}")
        if not allow_new_paths and not path_exists(prog, path):
            raise ValueError(
                f"Path does not exist for {pid}: {path} (use --allow-new-paths to create)"
            )
        if not skip_old_check:
            if path_exists(prog, path):
                current = get_path(prog, path)
            else:
                current = None
            if not _deep_equal(current, old_value):
                raise ValueError(
                    f"old_value mismatch for {pid} {path}: corpus={current!r} patch={old_value!r}"
                )
        set_path_flexible(prog, path, new_value, allow_new_paths=allow_new_paths)
        applied.append((pid, path))
    return applied


@click.command("merge-patch")
@click.argument("patch_file", type=click.Path(path_type=pathlib.Path, exists=True))
@click.option(
    "--allow-new-paths",
    is_flag=True,
    help="Allow creating missing object keys along the path (still requires program_id).",
)
@click.option(
    "--skip-old-check",
    is_flag=True,
    help="Do not verify old_value matches current corpus (dangerous).",
)
def merge_patch_cmd(
    patch_file: pathlib.Path,
    allow_new_paths: bool,
    skip_old_check: bool,
) -> None:
    """Merge a viewer-exported patch into corpus/programs.json."""
    root = find_repo_root()
    with patch_file.open(encoding="utf-8") as f:
        patch = json.load(f)
    errs = validate_patch_shape(root, patch)
    if errs:
        for e in errs:
            click.echo(e, err=True)
        sys.exit(1)

    corpus = load_corpus(root)
    try:
        applied = apply_merge_patch_to_corpus(
            corpus,
            patch,
            repo_root=root,
            allow_new_paths=allow_new_paths,
            skip_old_check=skip_old_check,
        )
    except ValueError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    enum_notes: list[str] = []
    val_errs = validate_corpus(
        root,
        corpus,
        category_repair_notes=enum_notes,
        repair_invalid_enums=True,
    )
    for line in enum_notes:
        click.echo(line, err=True)
    if val_errs:
        for e in val_errs:
            click.echo(e, err=True)
        click.echo("Patch rejected: merged corpus failed validation.", err=True)
        sys.exit(1)

    touched = {
        str(ch["program_id"])
        for ch in patch.get("changes", [])
        if isinstance(ch, dict) and ch.get("program_id") is not None
    }
    for pid in touched:
        prog = program_by_id(corpus, pid)
        if isinstance(prog, dict):
            bump_date_updated(prog)

    write_corpus(root, corpus)
    click.echo(f"Merged {len(applied)} change(s).")
    for pid, path in applied:
        click.echo(f"  {pid}  {path}")
