"""reevaluate-categories command."""

from __future__ import annotations

import json
import sys
from typing import Any

import click

from peer_atlas_cli.categories import CATEGORY_FILES, categories_payload_for_prompt, load_categories
from peer_atlas_cli.config import load_env, require_llm_config
from peer_atlas_cli.corpus_io import load_corpus, programs_list, write_corpus
from peer_atlas_cli.curriculum_units import recompute_normalized_unit_weights
from peer_atlas_cli.json_paths import set_path
from peer_atlas_cli.llm_client import get_client, parse_json_response
from peer_atlas_cli.program_merge import append_derivation_notes, extend_fields_needing_review
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


def _paths_for_program(program: dict[str, Any], category_keys: list[str]) -> list[str]:
    out: list[str] = []
    for key in category_keys:
        if key == "host_academic_models":
            out.append("identity.host_academic_model")
        elif key == "positioning_tags":
            tags = (
                (program.get("positioning") or {})
                .get("derived_features", {})
                .get("positioning_tags")
            )
            if isinstance(tags, list):
                for i in range(len(tags)):
                    out.append(f"positioning.derived_features.positioning_tags[{i}]")
            else:
                out.append("positioning.derived_features.positioning_tags")
        elif key == "duration_categories":
            out.append("duration.derived_features.duration_category")
        elif key == "cost_basis":
            out.append("degree_cost.derived_features.cost_basis")
        elif key == "unit_systems":
            out.append("curriculum.derived_features.unit_system")
        elif key == "sequencedness":
            out.append("curriculum.derived_features.sequencedness")
        elif key == "course_types":
            cur = program.get("curriculum") or {}
            for i, _ in enumerate(cur.get("core_courses") or []):
                out.append(f"curriculum.core_courses[{i}].primary_type")
                out.append(f"curriculum.core_courses[{i}].secondary_type")
        elif key == "verification_statuses":
            out.append("verification.status")
    return out


@click.command("reevaluate-categories")
@click.option(
    "--category",
    "category_keys",
    multiple=True,
    help="Category bundle key (e.g. positioning_tags, course_types). Repeatable. Default: all.",
)
@click.option(
    "--refresh-sources",
    is_flag=True,
    help="Re-fetch identity.source URLs (cached) and pass excerpts to the LLM.",
)
def reevaluate_categories_cmd(category_keys: tuple[str, ...], refresh_sources: bool) -> None:
    """Re-run LLM classification for fields tied to category vocabularies."""
    root = find_repo_root()
    load_env(root)
    provider, model, api_key, base_url = require_llm_config()

    keys = list(category_keys) if category_keys else list(CATEGORY_FILES.keys())
    unknown = [k for k in keys if k not in CATEGORY_FILES]
    if unknown:
        click.echo(f"Unknown category key(s): {unknown}", err=True)
        sys.exit(1)

    corpus = load_corpus(root)
    cat_bundle = load_categories(root)
    cat_json = categories_payload_for_prompt(cat_bundle)
    tmpl = load_prompt("reevaluate_categories.md")
    system = "You output only valid JSON. No prose."
    client = get_client(provider, api_key=api_key, model=model, base_url=base_url)

    worklist: list[tuple[dict[str, Any], list[str]]] = []
    for prog in programs_list(corpus):
        impacted = _paths_for_program(prog, keys)
        if impacted:
            worklist.append((prog, impacted))

    total = len(worklist)
    if total == 0:
        click.echo("No programs have fields impacted by the selected categories; nothing to do.")
        return

    click.echo(
        f"Calling LLM for {total} program(s) (model={model!r}) — each call is often 30–120s; "
        "429s retry with backoff (stderr).",
        err=True,
    )

    summary: dict[str, int] = {}

    for idx, (prog, impacted) in enumerate(worklist, start=1):
        pid = str(prog.get("program_id", ""))
        click.echo(f"  [{idx}/{total}] {pid} …", err=True)
        refreshed = ""
        if refresh_sources:
            parts: list[str] = []
            ident = prog.get("identity") or {}
            for s in (ident.get("sources") or [])[:3]:
                if isinstance(s, dict) and s.get("url"):
                    u = str(s["url"])
                    try:
                        parts.append(
                            f"=== {u} ===\n{fetch_url_text_cached(u, repo_root=root, max_chars=25_000, report=lambda m: click.echo(m, err=True), trace=lambda m: click.echo(f"  {m}", err=True))}"
                        )
                    except Exception as e:
                        click.echo(f"URL fetch failed (exception) {u}: {e}", err=True)
                        parts.append(f"=== {u} ===\n(fetch failed: {e})")
            refreshed = "\n\n".join(parts)
        user = render_template(
            tmpl,
            IMPACTED_PATHS="\n".join(impacted),
            PROGRAM=json.dumps(prog, indent=2, ensure_ascii=False),
            REFRESHED_SOURCES=refreshed,
            CATEGORIES=cat_json,
        )
        try:
            raw = client.complete(system=system, user=user)
        except RuntimeError as e:
            click.echo(f"{pid}: {e}", err=True)
            sys.exit(1)
        click.echo(f"     … response received for {pid}", err=True)
        try:
            payload = parse_json_response(raw)
        except json.JSONDecodeError as e:
            click.echo(f"{pid}: invalid JSON from LLM: {e}", err=True)
            sys.exit(1)
        updates = payload.get("updates") if isinstance(payload, dict) else None
        if not isinstance(updates, list):
            continue
        for u in updates:
            if not isinstance(u, dict):
                continue
            path = str(u.get("path", ""))
            if not path:
                continue
            set_path(prog, path, u.get("value"))
            summary[path] = summary.get(path, 0) + 1

        notes = payload.get("derivation_notes_to_append") if isinstance(payload, dict) else []
        if isinstance(notes, list):
            append_derivation_notes(prog, [n for n in notes if isinstance(n, dict)])

        extras = payload.get("fields_needing_review_additions") if isinstance(payload, dict) else []
        if isinstance(extras, list):
            extend_fields_needing_review(prog, [str(x) for x in extras])

        normalize_curriculum_electives_in_program(prog)
        recompute_normalized_unit_weights(prog)

    for prog in programs_list(corpus):
        strip_legacy_source_id_fields(prog)
        normalize_sources(prog)
        normalize_curriculum_electives_in_program(prog)
        normalize_core_course_learning_outcomes(prog)
        normalize_derivation_notes(prog, default_source_url=str(prog.get("base_url") or ""))

    errs = validate_corpus(root, corpus)
    if errs:
        for e in errs:
            click.echo(e, err=True)
        sys.exit(1)

    write_corpus(root, corpus)
    click.echo("Reevaluation complete. Touch counts by path:")
    for k in sorted(summary):
        click.echo(f"  {k}: {summary[k]}")
