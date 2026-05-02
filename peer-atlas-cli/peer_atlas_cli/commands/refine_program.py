"""refine-program command."""

from __future__ import annotations

import json
import sys

import click

from peer_atlas_cli.categories import categories_payload_for_prompt, load_categories
from peer_atlas_cli.config import load_env, require_llm_config
from peer_atlas_cli.corpus_io import load_corpus, program_by_id, programs_list, write_corpus
from peer_atlas_cli.curriculum_units import recompute_normalized_unit_weights
from peer_atlas_cli.json_paths import set_path
from peer_atlas_cli.llm_client import get_client, parse_json_response
from peer_atlas_cli.llm_reporting import echo_llm_raw_and_parsed
from peer_atlas_cli.program_merge import append_derivation_notes, extend_fields_needing_review
from peer_atlas_cli.program_sanitize import normalize_derivation_notes, normalize_sources, strip_legacy_source_id_fields
from peer_atlas_cli.prompt_loader import load_prompt, render_template
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.retrieval.evidence_bundle import gather_evidence_for_node
from peer_atlas_cli.retrieval.tavily_search import tavily_api_key
from peer_atlas_cli.schema_validation import validate_corpus


@click.command("refine-program")
@click.argument("program_id")
@click.argument("instruction")
@click.option(
    "--scope",
    default=None,
    metavar="NODE",
    help="Optional ingest node (e.g. positioning): attach Tavily+cached URL evidence to the prompt.",
)
def refine_program_cmd(program_id: str, instruction: str, scope: str | None) -> None:
    """Apply a targeted instruction to one program using the LLM."""
    root = find_repo_root()
    load_env(root)
    provider, model, api_key, base_url = require_llm_config()

    corpus = load_corpus(root)
    prog = program_by_id(corpus, program_id)
    if prog is None:
        click.echo(f"Unknown program_id: {program_id}", err=True)
        sys.exit(1)

    categories = load_categories(root)
    cat_json = categories_payload_for_prompt(categories)
    evidence = ""
    if scope:
        try:
            tavily_api_key()
        except RuntimeError as e:
            raise click.ClickException(str(e)) from e
        seed = ""
        ident = prog.get("identity") or {}
        for s in ident.get("sources") or []:
            if isinstance(s, dict) and s.get("url"):
                seed = str(s["url"])
                break
        evidence = gather_evidence_for_node(
            scope.strip(),
            prog,
            repo_root=root,
            seed_url=seed,
            user_query="",
            max_urls_total=6,
            report=lambda m: click.echo(m, err=True),
            trace=lambda m: click.echo(f"  {m}", err=True),
        )
    system = "You output only valid JSON. No prose."
    tmpl = load_prompt("refine_program.md")
    user = render_template(
        tmpl,
        PROGRAM=json.dumps(prog, indent=2, ensure_ascii=False),
        INSTRUCTION=instruction,
        EVIDENCE=evidence or "(none)",
        CATEGORIES=cat_json,
    )

    click.echo("Calling LLM for refinement — typically 30–120s; 429s retry with backoff (stderr).", err=True)

    client = get_client(provider, api_key=api_key, model=model, base_url=base_url)
    try:
        raw = client.complete(system=system, user=user)
    except RuntimeError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    click.echo("LLM response received; applying updates …", err=True)
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

    updates = payload.get("updates") if isinstance(payload, dict) else None
    if not isinstance(updates, list):
        click.echo("Expected updates array.", err=True)
        echo_llm_raw_and_parsed(
            raw,
            payload if isinstance(payload, dict) else None,
            intro="LLM output (missing or invalid updates array).",
        )
        sys.exit(1)

    changed: list[str] = []
    for u in updates:
        if not isinstance(u, dict):
            continue
        path = str(u.get("path", ""))
        if not path:
            continue
        set_path(prog, path, u.get("value"))
        changed.append(path)

    notes = payload.get("derivation_notes_to_append") if isinstance(payload, dict) else []
    if isinstance(notes, list):
        append_derivation_notes(prog, [n for n in notes if isinstance(n, dict)])

    extras = payload.get("fields_needing_review_additions") if isinstance(payload, dict) else []
    if isinstance(extras, list):
        extend_fields_needing_review(prog, [str(x) for x in extras])

    recompute_normalized_unit_weights(prog)

    strip_legacy_source_id_fields(prog)
    normalize_sources(prog)
    normalize_derivation_notes(prog, default_source_url=str(prog.get("base_url") or ""))

    errs = validate_corpus(root, corpus)
    if errs:
        echo_llm_raw_and_parsed(
            raw,
            prog,
            intro="Corpus validation failed after refine.",
            schema_errors=errs,
        )
        sys.exit(1)

    write_corpus(root, corpus)
    click.echo(f"Refined {program_id}. Updated paths:")
    for p in changed:
        click.echo(f"  {p}")
