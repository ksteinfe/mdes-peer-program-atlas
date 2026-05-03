"""add-program command — multi-step Tavily + per-node LLM ingest."""

from __future__ import annotations

import json
import sys
from typing import Any

import click

from peer_atlas_cli.categories import categories_payload_for_prompt, load_categories
from peer_atlas_cli.cli_progress import cli_bracket_line, cli_rule_line, cli_short_url
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
    run_search_context_from_seed,
)
from peer_atlas_cli.llm_reporting import echo_llm_raw_and_parsed, echo_validation_errors
from peer_atlas_cli.program_dates import bump_date_updated
from peer_atlas_cli.program_skeleton import (
    build_ingest_skeleton,
    set_ingest_stage,
    strip_atlas_ingest,
)
from peer_atlas_cli.program_sanitize import (
    ensure_course_source_urls,
    finalize_top_level_sources_into_rationales,
    migrate_course_source_id_to_url,
    normalize_core_course_learning_outcomes,
    normalize_curriculum_electives_in_program,
    normalize_derivation_notes,
    normalize_program_layout,
    strip_legacy_source_id_fields,
)
from peer_atlas_cli.publish_coerce import coerce_none_strings_for_publish
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.retrieval.evidence_bundle import (
    CORE_COURSE_MAX_RESULTS_PER_QUERY,
    fetch_pages_for_urls,
    fetch_url_text_cached,
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
    migrate_course_source_id_to_url(program)
    n_src = finalize_top_level_sources_into_rationales(program)
    if n_src:
        cli_bracket_line(
            "add",
            "sanitize",
            f"migrated {n_src} legacy source entr(y/ies) into llm_rationales.",
        )
    base = str(program.get("base_url") or "")
    n = normalize_derivation_notes(program, default_source_url=base)
    if n:
        cli_bracket_line(
            "add",
            "sanitize",
            f"normalized {n} llm_rationales entr(y/ies) (strings or legacy keys).",
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
    default=10,
    type=int,
    show_default=True,
    help="Max distinct URLs to fetch evidence from per node.",
)
@click.option(
    "--max-courses",
    default=12,
    type=click.IntRange(0, None),
    show_default=True,
    help="Max core_courses rows to run per-course evidence patches (0 = all rows).",
)
@click.option(
    "--curriculum-max-urls",
    default=10,
    type=int,
    show_default=True,
    help="Max URLs to fetch for curriculum_overview evidence (fewer, deeper pages).",
)
@click.option(
    "--evidence-budget-chars",
    default=0,
    type=int,
    show_default=True,
    help="Max combined characters of Markdown page excerpts in one evidence bundle (per node or per course batch); 0 = no cap.",
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
        bump_date_updated(program)
        _sanitize_before_validate(program)
        recompute_normalized_unit_weights(program)
        _append_or_replace_program(corpus, program)
        errs = validate_corpus(root, corpus)
        if errs:
            raise RuntimeError("corpus validation failed after ingest step")
        write_corpus(root, corpus)

    cli_rule_line("=")
    cli_bracket_line(
        "add",
        "setup",
        f"{model} · {provider} · {cli_short_url(host)} · tavily + fetch per node",
    )
    cli_rule_line("-")

    set_ingest_stage(program, "search_context")
    cli_bracket_line("add", "seed", f"search-context LLM · {cli_short_url(url)}")
    trace_seed = lambda m: cli_bracket_line("add", "seed", m, indent_tabs=1)

    def warn_seed(msg: str) -> None:
        cli_bracket_line("add", "seed", msg, indent_tabs=1)

    try:
        seed_md = fetch_url_text_cached(
            url,
            repo_root=root,
            llm_client=client,
            report=warn_seed,
            trace=trace_seed,
            warn_markdown_cap=warn_seed,
        )
    except Exception as e:
        cli_bracket_line("add", "seed", f"fetch skipped: {e}", indent_tabs=1)
        seed_md = ""
    if (seed_md or "").strip():
        run_search_context_from_seed(
            client=client,
            program=program,
            seed_markdown=seed_md,
            seed_url=url,
            repo_root=root,
        )

    for node in INGEST_MAIN_NODES:
        if node == "curriculum_overview":
            cli_rule_line("=")
            cli_bracket_line(
                "cv",
                "chain",
                "start (digest → overview → courses)",
            )
            cli_rule_line("-")
            set_ingest_stage(program, "curriculum_digest")
            urls = resolve_evidence_urls_for_node(
                node,
                program,
                seed_url=url,
                user_query=q,
                max_urls_total=curriculum_max_urls,
                repo_root=root,
            )

            def trace_cv(msg: str) -> None:
                cli_bracket_line("cv", "fetch", msg, indent_tabs=1)

            def fetch_warn_cv(msg: str) -> None:
                cli_bracket_line("cv", "fetch", msg, indent_tabs=1)

            if urls:
                trace_cv(f"queue {len(urls)} urls (full md)")
            pages = fetch_pages_for_urls(
                urls,
                repo_root=root,
                llm_client=client,
                report=fetch_warn_cv,
                trace=trace_cv,
            )
            ctx_json = program_context_json_for_curriculum_steps(program)
            dense_pairs: list[tuple[str, str]] = []
            for src_url, page_text in pages:
                try:
                    pt_n = len(page_text or "")
                    cli_bracket_line(
                        "cv",
                        "dense",
                        f"LLM · {cli_short_url(src_url)} · page {pt_n}c",
                        indent_tabs=1,
                    )
                    dense = run_curriculum_source_dense_extract_step(
                        client=client,
                        program_context_json=ctx_json,
                        source_url=src_url,
                        page_text=page_text,
                        repo_root=root,
                    )
                except (ValueError, RuntimeError) as e:
                    cli_bracket_line(
                        "cv",
                        "dense",
                        f"fail · {cli_short_url(src_url)} · {e}",
                        indent_tabs=1,
                    )
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
                cli_bracket_line(
                    "cv",
                    "overview",
                    f"LLM · mash {len(mashed)}c",
                    indent_tabs=1,
                )
                raw = run_curriculum_overview_step(
                    client=client,
                    program=program,
                    evidence=mashed,
                    categories_json=cat_json,
                    program_context_json=ctx_json,
                    repo_root=root,
                )
            except LLMSchemaValidationError as e:
                cli_bracket_line("cv", "overview", f"fail schema: {e}")
                echo_llm_raw_and_parsed(
                    e.raw,
                    program,
                    intro=f"Ingest failed at node {node!r}.",
                    schema_errors=e.errors,
                )
                sys.exit(1)
            except (json.JSONDecodeError, ValueError, RuntimeError) as e:
                cli_bracket_line("cv", "overview", f"fail: {e}")
                echo_llm_raw_and_parsed(
                    raw,
                    program,
                    intro=f"Ingest failed at node {node!r}.",
                )
                sys.exit(1)
            set_ingest_stage(program, "curriculum_courses")
            courses = (program.get("curriculum") or {}).get("core_courses") or []
            # Per-course Tavily + LLM patch applies only to core_courses[].
            # curriculum.electives (summary + estimated count) is filled by the curriculum_overview LLM from program policy text (no per-elective-course research).
            n_courses = len(courses)
            if max_courses > 0:
                n_courses = min(n_courses, max_courses)
            for i in range(n_courses):
                cli_bracket_line(
                    "cv",
                    f"c[{i}]",
                    "tavily + fetch",
                    indent_tabs=1,
                )
                cq = queries_for_core_course(
                    program,
                    str(courses[i].get("course_title") or ""),
                    str(courses[i].get("course_id") or ""),
                    seed_url=url,
                    user_query=q,
                    repo_root=root,
                )
                set_ingest_stage(program, "curriculum_course_research")
                ev_c = gather_evidence_for_queries(
                    cq,
                    llm_client=client,
                    repo_root=root,
                    seed_url=url,
                    max_results_per_query=CORE_COURSE_MAX_RESULTS_PER_QUERY,
                    max_urls_total=min(5, max_search_urls),
                    budget_chars=evidence_budget_chars,
                    report=fetch_warn_cv,
                    trace=trace_cv,
                )
                cli_bracket_line(
                    "cv",
                    f"c[{i}]",
                    f"{len(cq)} queries · evidence {len(ev_c)}c",
                    indent_tabs=1,
                )
                set_ingest_stage(program, "curriculum_course_llm")
                try:
                    cli_bracket_line(
                        "cv",
                        f"p[{i}]",
                        f"LLM · {len(ev_c)}c",
                        indent_tabs=1,
                    )
                    run_curriculum_course_patch(
                        client=client,
                        program=program,
                        index=i,
                        evidence=ev_c,
                        categories_json=cat_json,
                        repo_root=root,
                    )
                except LLMSchemaValidationError as e:
                    cli_bracket_line(
                        "cv",
                        f"p[{i}]",
                        f"fail schema: {e}",
                        indent_tabs=1,
                    )
                    echo_llm_raw_and_parsed(
                        e.raw,
                        program,
                        intro=f"Course patch index {i}.",
                        schema_errors=e.errors,
                    )
                    sys.exit(1)
                except (json.JSONDecodeError, ValueError, RuntimeError) as e:
                    cli_bracket_line(
                        "cv",
                        f"p[{i}]",
                        f"fail: {e}",
                        indent_tabs=1,
                    )
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
            cli_rule_line("-")
            continue

        cli_rule_line("=")
        task_label = "node"
        cli_bracket_line(node, task_label, "start")
        cli_rule_line("-")
        set_ingest_stage(program, node)

        def trace_node(msg: str) -> None:
            cli_bracket_line(node, "fetch", msg, indent_tabs=1)

        def fetch_warn_node(msg: str) -> None:
            cli_bracket_line(node, "fetch", msg, indent_tabs=1)

        evidence = gather_evidence_for_node(
            node,
            program,
            llm_client=client,
            repo_root=root,
            seed_url=url,
            user_query=q,
            max_urls_total=max_search_urls,
            budget_chars=evidence_budget_chars,
            report=fetch_warn_node,
            trace=trace_node,
        )
        raw = ""
        try:
            cli_bracket_line(
                node,
                "json",
                f"LLM · evidence {len(evidence)}c",
                indent_tabs=1,
            )
            raw = run_node_step(
                client=client,
                program=program,
                node=node,
                evidence=evidence,
                categories_json=cat_json,
                repo_root=root,
            )
        except LLMSchemaValidationError as e:
            cli_bracket_line(node, "json", f"fail schema: {e}")
            echo_llm_raw_and_parsed(
                e.raw,
                program,
                intro=f"Ingest failed at node {node!r}.",
                schema_errors=e.errors,
            )
            sys.exit(1)
        except (json.JSONDecodeError, ValueError, RuntimeError) as e:
            cli_bracket_line(node, "json", f"fail: {e}")
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
        cli_rule_line("-")

    cli_rule_line("=")
    cli_bracket_line(
        "add",
        "finalize",
        "validate + write …",
    )
    cli_rule_line("-")

    set_ingest_stage(program, "complete")
    strip_atlas_ingest(program)
    bump_date_updated(program)
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
            cli_bracket_line("add", "finalize", "dry-run OK")
    cli_rule_line("=")
    cli_bracket_line(
        "add",
        "done",
        f"{'added ' + pid if not dry_run else 'dry-run ' + pid}",
    )
