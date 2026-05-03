"""reconsider-node — re-run one ingest node with human instruction + rationale fetches."""

from __future__ import annotations

import json
import sys
from typing import Any

import click

from peer_atlas_cli.categories import categories_payload_for_prompt, load_categories
from peer_atlas_cli.config import load_env, require_llm_config
from peer_atlas_cli.corpus_io import load_corpus, program_by_id, write_corpus
from peer_atlas_cli.llm_client import get_client
from peer_atlas_cli.llm_nodes import (
    LLMSchemaValidationError,
    program_context_json_for_curriculum_steps,
    run_curriculum_overview_step,
    run_node_step,
)
from peer_atlas_cli.llm_reporting import echo_llm_raw_and_parsed, echo_validation_errors
from peer_atlas_cli.program_sanitize import (
    ensure_course_source_urls,
    normalize_core_course_learning_outcomes,
    normalize_curriculum_electives_in_program,
    normalize_derivation_notes,
    normalize_program_layout,
    normalize_sources,
    strip_legacy_source_id_fields,
)
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.reconsider_evidence import (
    RECONSIDER_NODES,
    build_reconsider_evidence,
    fetch_rationale_source_pages,
    rationales_for_node,
)
from peer_atlas_cli.curriculum_units import recompute_normalized_unit_weights
from peer_atlas_cli.schema_validation import validate_corpus


def _sanitize_program(program: dict[str, Any], *, base_url: str) -> None:
    normalize_program_layout(program)
    strip_legacy_source_id_fields(program)
    normalize_sources(program)
    normalize_derivation_notes(program, default_source_url=base_url)
    ensure_course_source_urls(program, base_url)
    normalize_core_course_learning_outcomes(program)
    normalize_curriculum_electives_in_program(program)


@click.command("reconsider-node")
@click.argument("program_id")
@click.argument(
    "node",
    type=click.Choice(sorted(RECONSIDER_NODES), case_sensitive=False),
)
@click.argument("instruction", nargs=-1, required=True)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Call the LLM and validate but do not write corpus/programs.json.",
)
@click.option(
    "--max-chars-per-url",
    default=12_000,
    type=int,
    show_default=True,
    help="Max characters stored per fetched rationale source_url.",
)
@click.option(
    "--max-total-chars",
    default=48_000,
    type=int,
    show_default=True,
    help="Total character budget for all rationale fetches combined.",
)
@click.option(
    "--max-llm-attempts",
    default=3,
    type=int,
    show_default=True,
    help="Schema-aware retries for the LLM response.",
)
def reconsider_node_cmd(
    program_id: str,
    node: str,
    instruction: tuple[str, ...],
    dry_run: bool,
    max_chars_per_url: int,
    max_total_chars: int,
    max_llm_attempts: int,
) -> None:
    """
    Re-run a single corpus node for PROGRAM_ID using the same prompts/rules as ingest,
    plus your INSTRUCTION and relevant llm_rationales (with fetched pages for their
    source_url values). The LLM may return new top-level ``llm_rationales`` rows; those
    are **appended** to the program (existing rationales are kept) alongside the
    updated node subtree.

    NODE: positioning | duration | degree_cost | curriculum | curriculum_overview |
    identity | verification

    Use quotes for INSTRUCTION if it contains spaces, or pass multiple words after NODE.
    """
    root = find_repo_root()
    load_env(root)
    provider, model, api_key, base_llm_url = require_llm_config()

    pid = (program_id or "").strip()
    if not pid:
        raise click.UsageError("program_id must be non-empty.")

    node_key = node.strip().lower()
    instr = " ".join(instruction).strip()
    if not instr:
        raise click.UsageError("instruction must be non-empty.")

    corpus = load_corpus(root)
    program = program_by_id(corpus, pid)
    if program is None:
        raise click.ClickException(f"Unknown program_id: {pid!r}")

    cats = load_categories(root)
    cat_json = categories_payload_for_prompt(cats)

    rel = rationales_for_node(node_key, program)
    fetched = fetch_rationale_source_pages(
        root,
        rel,
        max_chars_per_url=max_chars_per_url,
        max_total_chars=max_total_chars,
        report=lambda m: click.echo(m, err=True),
        trace=lambda m: click.echo(f"  {m}", err=True),
    )
    evidence = build_reconsider_evidence(
        user_instruction=instr,
        rationales=rel,
        fetched_pages=fetched,
        primary_response_key="curriculum"
        if node_key == "curriculum_overview"
        else node_key,
    )

    client = get_client(provider, api_key=api_key, model=model, base_url=base_llm_url)
    host = base_llm_url or "https://api.openai.com"
    click.echo(
        f"reconsider-node: program={pid!r} node={node_key!r} model={model!r} "
        f"provider={provider} at {host!r}; rationales={len(rel)}",
        err=True,
    )

    raw = ""
    try:
        if node_key == "curriculum_overview":
            ctx_json = program_context_json_for_curriculum_steps(program)
            preserved_summary = ""
            cprev = program.get("curriculum")
            if isinstance(cprev, dict):
                ps = cprev.get("evidence_curriculum_summary")
                if isinstance(ps, str):
                    preserved_summary = ps
            raw = run_curriculum_overview_step(
                client=client,
                program=program,
                evidence=evidence,
                categories_json=cat_json,
                program_context_json=ctx_json,
                curriculum_digest="",
                evidence_curriculum_summary=preserved_summary,
                repo_root=root,
                max_llm_attempts=max_llm_attempts,
            )
        else:
            raw = run_node_step(
                client=client,
                program=program,
                node=node_key,
                evidence=evidence,
                categories_json=cat_json,
                repo_root=root,
                max_llm_attempts=max_llm_attempts,
            )
    except LLMSchemaValidationError as e:
        click.echo(f"reconsider-node failed (schema): {e}", err=True)
        echo_llm_raw_and_parsed(
            e.raw,
            program,
            intro="reconsider-node LLM output rejected by schema.",
            schema_errors=e.errors,
        )
        sys.exit(1)
    except (json.JSONDecodeError, ValueError, RuntimeError) as e:
        click.echo(f"reconsider-node failed: {e}", err=True)
        echo_llm_raw_and_parsed(raw, program, intro="reconsider-node failure.")
        sys.exit(1)

    base = str(program.get("base_url") or "")
    _sanitize_program(program, base_url=base)
    if node_key in ("curriculum", "curriculum_overview"):
        recompute_normalized_unit_weights(program)

    errs = validate_corpus(root, corpus)
    if errs:
        echo_validation_errors(errs, intro="Corpus invalid after reconsider-node.")
        sys.exit(1)

    if dry_run:
        click.echo("Dry run: OK (not writing corpus).", err=True)
        return

    write_corpus(root, corpus)
    click.echo(f"Wrote corpus with updated {node_key!r} for {pid!r}.", err=True)
