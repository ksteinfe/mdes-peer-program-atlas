"""add-program command — multi-step Tavily + per-node LLM ingest."""

from __future__ import annotations

import json
import sys
from typing import Any

import click

from peer_atlas_cli.categories import categories_payload_for_prompt, load_categories
from peer_atlas_cli.config import load_env, require_llm_config
from peer_atlas_cli.corpus_io import load_corpus, programs_list, write_corpus
from peer_atlas_cli.curriculum_units import recompute_normalized_unit_weights
from peer_atlas_cli.identity_fallback import apply_identity_fallbacks
from peer_atlas_cli.llm_client import get_client
from peer_atlas_cli.llm_nodes import (
    INGEST_MAIN_NODES,
    LLMSchemaValidationError,
    program_context_json_for_curriculum_steps,
    run_curriculum_course_patch,
    run_curriculum_overview_step,
    run_curriculum_source_dense_extract_step,
    run_node_step,
)
from peer_atlas_cli.llm_reporting import echo_llm_raw_and_parsed, echo_validation_errors
from peer_atlas_cli.program_skeleton import (
    build_ingest_skeleton,
    set_ingest_stage,
    strip_atlas_ingest,
)
from peer_atlas_cli.program_sanitize import (
    ensure_course_source_urls,
    normalize_core_course_learning_outcomes,
    normalize_curriculum_electives_in_program,
    normalize_derivation_notes,
    normalize_program_layout,
    normalize_sources,
    strip_legacy_source_id_fields,
)
from peer_atlas_cli.publish_coerce import coerce_none_strings_for_publish
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.retrieval.evidence_bundle import (
    fetch_pages_for_urls,
    gather_evidence_for_node,
    gather_evidence_for_queries,
    mash_curriculum_source_summaries,
    resolve_evidence_urls_for_node,
)
from peer_atlas_cli.retrieval.query_builders import queries_for_core_course
from peer_atlas_cli.retrieval.tavily_search import tavily_api_key
from peer_atlas_cli.schema_validation import validate_corpus


def _append_or_replace_program(corpus: dict[str, Any], program: dict[str, Any]) -> None:
    plist = programs_list(corpus)
    pid = program.get("program_id")
    for i, p in enumerate(plist):
        if isinstance(p, dict) and p.get("program_id") == pid:
            plist[i] = program
            return
    plist.append(program)


def _remove_program_by_id(corpus: dict[str, Any], program_id: str) -> None:
    plist = programs_list(corpus)
    for i, p in enumerate(plist):
        if isinstance(p, dict) and p.get("program_id") == program_id:
            plist.pop(i)
            return


def _sanitize_before_validate(program: dict[str, Any]) -> None:
    normalize_program_layout(program)
    strip_legacy_source_id_fields(program)
    normalize_sources(program)
    base = str(program.get("base_url") or "")
    n = normalize_derivation_notes(program, default_source_url=base)
    if n:
        click.echo(
            f"Note: normalized {n} llm_rationales entr(y/ies) (strings or legacy keys).",
            err=True,
        )
    ensure_course_source_urls(program, base)
    normalize_core_course_learning_outcomes(program)
    normalize_curriculum_electives_in_program(program)


@click.command("add-program")
@click.argument("base_url")
@click.argument("program_id")
@click.argument("query", required=False, default="")
@click.option(
    "--max-search-urls",
    default=8,
    type=int,
    show_default=True,
    help="Max distinct URLs to fetch evidence from per node.",
)
@click.option(
    "--max-courses",
    default=8,
    type=click.IntRange(0, None),
    show_default=True,
    help="Max core_courses rows to run per-course evidence patches (0 = all rows).",
)
@click.option(
    "--curriculum-max-urls",
    default=4,
    type=int,
    show_default=True,
    help="Max URLs to fetch for curriculum_overview evidence (fewer, deeper pages).",
)
@click.option(
    "--curriculum-max-chars-per-url",
    default=120_000,
    type=int,
    show_default=True,
    help="Max characters per fetched URL for curriculum_overview; 0 = very large cap. Fetch layer may still bound body size.",
)
@click.option(
    "--curriculum-budget-chars",
    default=0,
    type=int,
    show_default=True,
    help="Unused for curriculum_overview (per-URL fetch + per-URL LLM extract); kept for CLI compatibility. Other behavior unchanged.",
)
@click.option(
    "--max-chars-per-url",
    default=120_000,
    type=int,
    show_default=True,
    help="Per fetched evidence URL for node steps and per-course research. Values >= 50_000 use the fetch coalesce floor (~8 MiB). 0 = 1M before coalesce.",
)
@click.option(
    "--evidence-budget-chars",
    default=0,
    type=int,
    show_default=True,
    help="Max combined characters for fetched excerpts in one evidence bundle (per node or per course batch); 0 = no cap.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Run LLM steps but do not write the corpus file.",
)
def add_program_cmd(
    base_url: str,
    program_id: str,
    query: str,
    max_search_urls: int,
    max_courses: int,
    curriculum_max_urls: int,
    curriculum_max_chars_per_url: int,
    curriculum_budget_chars: int,
    max_chars_per_url: int,
    evidence_budget_chars: int,
    dry_run: bool,
) -> None:
    """Create a new program via search-backed, per-node LLM ingest."""
    root = find_repo_root()
    load_env(root)
    provider, model, api_key, base_llm_url = require_llm_config()
    try:
        tavily_api_key()
    except RuntimeError as e:
        raise click.ClickException(str(e)) from e

    url = (base_url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise click.UsageError("base_url must start with http:// or https://")

    pid = (program_id or "").strip()
    if not pid:
        raise click.UsageError("program_id must be non-empty.")

    q = (query or "").strip()

    corpus = load_corpus(root)
    existing_ids = {p.get("program_id") for p in programs_list(corpus)}
    if pid in existing_ids:
        raise click.UsageError(
            f"program_id {pid!r} already exists in corpus; choose another id or remove the row first."
        )

    categories = load_categories(root)
    cat_json = categories_payload_for_prompt(categories)

    program = build_ingest_skeleton(pid, url)
    apply_identity_fallbacks(program, url=url, query=q)

    client = get_client(provider, api_key=api_key, model=model, base_url=base_llm_url)
    host = base_llm_url or "https://api.openai.com"

    if not dry_run:
        _append_or_replace_program(corpus, program)
        errs = validate_corpus(root, corpus)
        if errs:
            echo_validation_errors(errs, intro="Draft skeleton failed validation.")
            _remove_program_by_id(corpus, pid)
            raise click.ClickException("draft skeleton failed validation")
        write_corpus(root, corpus)

    def persist() -> None:
        if dry_run:
            return
        _sanitize_before_validate(program)
        recompute_normalized_unit_weights(program)
        _append_or_replace_program(corpus, program)
        errs = validate_corpus(root, corpus)
        if errs:
            raise RuntimeError("corpus validation failed after ingest step")
        write_corpus(root, corpus)

    click.echo(
        f"Ingest pipeline (model={model!r}, provider={provider}) at {host!r}; "
        "Tavily search + cached fetch per node.",
        err=True,
    )

    def fetch_warn(msg: str) -> None:
        click.echo(msg, err=True)

    def trace_source(msg: str) -> None:
        click.echo(f"  {msg}", err=True)

    for node in INGEST_MAIN_NODES:
        if node == "curriculum_overview":
            set_ingest_stage(program, "curriculum_digest")
            click.echo(
                f"--- Node: {node} (per-source curriculum extract + overview) ---",
                err=True,
            )
            urls = resolve_evidence_urls_for_node(
                node,
                program,
                seed_url=url,
                user_query=q,
                max_urls_total=curriculum_max_urls,
            )
            if urls:
                per_url = curriculum_max_chars_per_url if curriculum_max_chars_per_url > 0 else 1_000_000
                trace_source(
                    f"evidence: queueing {len(urls)} source URL(s); "
                    f"no per-source char cap for LLM extract "
                    f"(fetch up to {per_url} chars per URL)"
                )
            pages = fetch_pages_for_urls(
                urls,
                repo_root=root,
                max_chars_per_url=curriculum_max_chars_per_url,
                report=fetch_warn,
                trace=trace_source,
                llm_client=client,
            )
            ctx_json = program_context_json_for_curriculum_steps(program)
            dense_pairs: list[tuple[str, str]] = []
            for src_url, page_text in pages:
                try:
                    click.echo(
                        f"Calling LLM (curriculum source extract) … {src_url}",
                        err=True,
                    )
                    dense = run_curriculum_source_dense_extract_step(
                        client=client,
                        program_context_json=ctx_json,
                        source_url=src_url,
                        page_text=page_text,
                        repo_root=root,
                    )
                except (ValueError, RuntimeError) as e:
                    click.echo(f"curriculum source extract failed for {src_url!r}: {e}", err=True)
                    sys.exit(1)
                dense_pairs.append((src_url, dense))
            mashed = mash_curriculum_source_summaries(dense_pairs).strip()
            if not mashed:
                mashed = (
                    "(No dense curriculum extracts produced; page fetches may have failed "
                    "or returned no extractable text.)"
                )

            set_ingest_stage(program, "curriculum_overview")
            raw = ""
            try:
                click.echo("Calling LLM (curriculum overview JSON) …", err=True)
                raw = run_curriculum_overview_step(
                    client=client,
                    program=program,
                    evidence=mashed,
                    categories_json=cat_json,
                    program_context_json=ctx_json,
                    repo_root=root,
                )
            except LLMSchemaValidationError as e:
                click.echo(f"{node} step failed (schema): {e}", err=True)
                echo_llm_raw_and_parsed(
                    e.raw,
                    program,
                    intro=f"Ingest failed at node {node!r}.",
                    schema_errors=e.errors,
                )
                sys.exit(1)
            except (json.JSONDecodeError, ValueError, RuntimeError) as e:
                click.echo(f"{node} step failed: {e}", err=True)
                echo_llm_raw_and_parsed(
                    raw,
                    program,
                    intro=f"Ingest failed at node {node!r}.",
                )
                sys.exit(1)
            set_ingest_stage(program, "curriculum_courses")
            courses = (program.get("curriculum") or {}).get("core_courses") or []
            # Per-course Tavily + LLM patch applies only to core_courses[].
            # elective_requirements (string) + elective_courses[] are filled by the curriculum_overview LLM from program policy text only (no per-slot research).
            n_courses = len(courses)
            if max_courses > 0:
                n_courses = min(n_courses, max_courses)
            for i in range(n_courses):
                click.echo(f"  curriculum course index {i} …", err=True)
                cq = queries_for_core_course(
                    program,
                    str(courses[i].get("course_title") or ""),
                    str(courses[i].get("course_id") or ""),
                    seed_url=url,
                )
                set_ingest_stage(program, "curriculum_course_research")
                ev_c = gather_evidence_for_queries(
                    cq,
                    repo_root=root,
                    seed_url=url,
                    max_urls_total=min(5, max_search_urls),
                    max_chars_per_url=max_chars_per_url,
                    budget_chars=evidence_budget_chars,
                    report=fetch_warn,
                    trace=trace_source,
                    llm_client=client,
                )
                click.echo(
                    f"  research done for core course index {i} ({len(cq)} queries).",
                    err=True,
                )
                set_ingest_stage(program, "curriculum_course_llm")
                try:
                    run_curriculum_course_patch(
                        client=client,
                        program=program,
                        index=i,
                        evidence=ev_c,
                        categories_json=cat_json,
                        repo_root=root,
                    )
                except LLMSchemaValidationError as e:
                    click.echo(f"curriculum patch {i} failed (schema): {e}", err=True)
                    echo_llm_raw_and_parsed(
                        e.raw,
                        program,
                        intro=f"Course patch index {i}.",
                        schema_errors=e.errors,
                    )
                    sys.exit(1)
                except (json.JSONDecodeError, ValueError, RuntimeError) as e:
                    click.echo(f"curriculum patch {i} failed: {e}", err=True)
                    sys.exit(1)
            try:
                persist()
            except RuntimeError:
                errs_post = validate_corpus(root, corpus)
                echo_llm_raw_and_parsed(
                    raw,
                    program,
                    intro="Post-curriculum validation failed.",
                    schema_errors=errs_post,
                )
                sys.exit(1)
            continue

        set_ingest_stage(program, node)
        click.echo(f"--- Node: {node} ---", err=True)
        evidence = gather_evidence_for_node(
            node,
            program,
            repo_root=root,
            seed_url=url,
            user_query=q,
            max_urls_total=max_search_urls,
            max_chars_per_url=max_chars_per_url,
            budget_chars=evidence_budget_chars,
            report=fetch_warn,
            trace=trace_source,
            llm_client=client,
        )
        raw = ""
        try:
            click.echo("Calling LLM …", err=True)
            raw = run_node_step(
                client=client,
                program=program,
                node=node,
                evidence=evidence,
                categories_json=cat_json,
                repo_root=root,
            )
        except LLMSchemaValidationError as e:
            click.echo(f"{node} step failed (schema): {e}", err=True)
            echo_llm_raw_and_parsed(
                e.raw,
                program,
                intro=f"Ingest failed at node {node!r}.",
                schema_errors=e.errors,
            )
            sys.exit(1)
        except (json.JSONDecodeError, ValueError, RuntimeError) as e:
            click.echo(f"{node} step failed: {e}", err=True)
            echo_llm_raw_and_parsed(raw, program, intro=f"Ingest failed at node {node!r}.")
            sys.exit(1)
        try:
            persist()
        except RuntimeError:
            errs_post = validate_corpus(root, corpus)
            echo_llm_raw_and_parsed(
                raw,
                program,
                intro="Post-step validation failed.",
                schema_errors=errs_post,
            )
            sys.exit(1)

    set_ingest_stage(program, "complete")
    strip_atlas_ingest(program)
    _sanitize_before_validate(program)
    coerce_none_strings_for_publish(program)

    if not dry_run:
        recompute_normalized_unit_weights(program)
        _append_or_replace_program(corpus, program)
        errs = validate_corpus(root, corpus)
        if errs:
            echo_llm_raw_and_parsed(
                "",
                program,
                intro="Final strict validation failed. Fix corpus manually or use merge-patch.",
                schema_errors=errs,
            )
            sys.exit(1)
        write_corpus(root, corpus)
    else:
        recompute_normalized_unit_weights(program)
        meta = corpus.get("corpus_metadata")
        if not isinstance(meta, dict):
            meta = {}
        errs_dr = validate_corpus(root, {"programs": [program], "corpus_metadata": meta})
        if errs_dr:
            echo_validation_errors(
                errs_dr,
                intro="(dry-run: would not pass final strict validation)",
            )
        else:
            click.echo("(dry-run: final strict validation OK)", err=True)

    click.echo(f"Added program {pid}" if not dry_run else f"Dry-run finished for {pid}")
