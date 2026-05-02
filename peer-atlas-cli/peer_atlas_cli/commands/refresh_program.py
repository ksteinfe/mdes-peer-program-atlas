"""refresh-program command."""

from __future__ import annotations

import copy
import json
import sys

import click

from peer_atlas_cli.categories import categories_payload_for_prompt, load_categories
from peer_atlas_cli.config import load_env, require_llm_config
from peer_atlas_cli.corpus_io import load_corpus, program_by_id, programs_list, write_corpus
from peer_atlas_cli.curriculum_units import recompute_normalized_unit_weights
from peer_atlas_cli.llm_client import get_client, parse_json_response
from peer_atlas_cli.llm_reporting import echo_llm_raw_and_parsed
from peer_atlas_cli.program_merge import (
    apply_human_scope_preservation,
    extend_fields_needing_review,
    merge_sources_keep_existing,
)
from peer_atlas_cli.program_sanitize import (
    normalize_core_course_learning_outcomes,
    normalize_curriculum_electives_in_program,
    normalize_derivation_notes,
    normalize_sources,
    strip_legacy_source_id_fields,
)
from peer_atlas_cli.prompt_loader import load_prompt, render_template
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.retrieval.fetch_cached import fetch_url_text_cached
from peer_atlas_cli.schema_validation import validate_corpus


def _diff_paths(old: dict, new: dict, prefix: str = "") -> list[str]:
    changes: list[str] = []
    if isinstance(old, dict) and isinstance(new, dict):
        keys = set(old) | set(new)
        for k in sorted(keys, key=str):
            p = f"{prefix}.{k}" if prefix else str(k)
            ov, nv = old.get(k, None), new.get(k, None)
            if k not in old:
                changes.append(f"{p} (added)")
            elif k not in new:
                changes.append(f"{p} (removed)")
            elif isinstance(ov, dict) and isinstance(nv, dict):
                changes.extend(_diff_paths(ov, nv, p))
            elif isinstance(ov, list) and isinstance(nv, list):
                if json.dumps(ov, sort_keys=True) != json.dumps(nv, sort_keys=True):
                    changes.append(p)
            elif ov != nv:
                changes.append(p)
    return changes


@click.command("refresh-program")
@click.argument("program_id")
@click.option(
    "--overwrite-human-reviewed",
    is_flag=True,
    help="Allow overwriting sections even when verification.status is human_reviewed.",
)
def refresh_program_cmd(program_id: str, overwrite_human_reviewed: bool) -> None:
    """Re-research an existing program and merge updates into the corpus."""
    root = find_repo_root()
    load_env(root)
    provider, model, api_key, base_url = require_llm_config()

    corpus = load_corpus(root)
    old = program_by_id(corpus, program_id)
    if old is None:
        click.echo(f"Unknown program_id: {program_id}", err=True)
        sys.exit(1)

    urls: list[str] = []
    ident = old.get("identity") or {}
    for s in ident.get("sources") or []:
        if isinstance(s, dict) and s.get("url"):
            urls.append(str(s["url"]))
    fetched_parts: list[str] = []
    if urls:
        click.echo(f"Fetching up to {min(3, len(urls))} source URL(s) …", err=True)
    for u in urls[:3]:
        try:
            fetched_parts.append(
                f"=== URL {u} ===\n{fetch_url_text_cached(u, repo_root=root, max_chars=40_000, report=lambda m: click.echo(m, err=True), trace=lambda m: click.echo(f"  {m}", err=True))}"
            )
        except Exception as e:
            click.echo(f"URL fetch failed (exception) {u}: {e}", err=True)
            fetched_parts.append(f"=== URL {u} ===\n(fetch failed: {e})")
    fetched = "\n\n".join(fetched_parts)

    categories = load_categories(root)
    cat_json = categories_payload_for_prompt(categories)
    system = "You output only valid JSON. No prose."
    tmpl = load_prompt("refresh_program.md")
    user = render_template(
        tmpl,
        PROGRAM=json.dumps(old, indent=2, ensure_ascii=False),
        FETCHED=fetched,
        CATEGORIES=cat_json,
    )

    click.echo("Calling LLM for refresh — typically 30–120s; 429s retry with backoff (stderr).", err=True)

    client = get_client(provider, api_key=api_key, model=model, base_url=base_url)
    try:
        raw = client.complete(system=system, user=user)
    except RuntimeError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    click.echo("LLM response received; merging and validating …", err=True)
    try:
        payload = parse_json_response(raw)
    except json.JSONDecodeError as e:
        click.echo(f"LLM did not return valid JSON: {e}", err=True)
        echo_llm_raw_and_parsed(
            raw,
            None,
            intro="See raw response below (JSON parse failed).",
        )
        sys.exit(1)

    merged = payload.get("merged_program") if isinstance(payload, dict) else None
    if not isinstance(merged, dict):
        click.echo("Expected merged_program object in LLM output.", err=True)
        echo_llm_raw_and_parsed(
            raw,
            payload if isinstance(payload, dict) else None,
            intro="LLM output (missing or invalid merged_program).",
        )
        sys.exit(1)

    merged = copy.deepcopy(merged)
    merged["program_id"] = program_id

    apply_human_scope_preservation(
        old, merged, overwrite=overwrite_human_reviewed
    )
    merge_sources_keep_existing(old, merged)

    extras = payload.get("fields_needing_review_additions") if isinstance(payload, dict) else []
    if isinstance(extras, list):
        extend_fields_needing_review(merged, [str(x) for x in extras])

    normalize_curriculum_electives_in_program(merged)
    recompute_normalized_unit_weights(merged)

    strip_legacy_source_id_fields(merged)
    normalize_sources(merged)
    normalize_core_course_learning_outcomes(merged)
    normalize_derivation_notes(
        merged, default_source_url=str(merged.get("base_url") or "")
    )

    diff = _diff_paths(old, merged)
    plist = programs_list(corpus)
    for i, p in enumerate(plist):
        if p.get("program_id") == program_id:
            plist[i] = merged
            break

    errs = validate_corpus(root, corpus)
    if errs:
        echo_llm_raw_and_parsed(
            raw,
            merged,
            intro="Corpus validation failed after refresh merge.",
            schema_errors=errs,
        )
        sys.exit(1)

    write_corpus(root, corpus)
    click.echo(f"Refreshed {program_id}. Changed paths ({len(diff)}):")
    for line in diff[:200]:
        click.echo(f"  {line}")
    if len(diff) > 200:
        click.echo("  ...")
