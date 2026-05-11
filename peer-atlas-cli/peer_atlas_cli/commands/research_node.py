"""research-node — fresh Tavily search + LLM step for one node on an existing program."""

from __future__ import annotations

import json
import sys
from typing import Any

import click

from peer_atlas_cli.categories import categories_payload_for_prompt, load_categories
from peer_atlas_cli.cli_progress import cli_bracket_line, cli_rule_line, cli_short_url
from peer_atlas_cli.config import load_env, require_llm_config
from peer_atlas_cli.corpus_io import load_corpus, program_by_id, write_corpus
from peer_atlas_cli.program_dates import bump_date_updated
from peer_atlas_cli.llm_client import get_client
from peer_atlas_cli.llm_nodes import LLMSchemaValidationError, run_node_step
from peer_atlas_cli.llm_reporting import echo_llm_raw_and_parsed, echo_validation_errors
from peer_atlas_cli.program_sanitize import normalize_llm_rationales, normalize_program_layout
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.retrieval.evidence_bundle import gather_evidence_for_node
from peer_atlas_cli.retrieval.tavily_search import tavily_api_key
from peer_atlas_cli.schema_validation import validate_corpus

RESEARCH_NODES: frozenset[str] = frozenset(
    {
        "positioning",
        "duration",
        "degree_cost",
        "identity",
        "historical",
        "verification",
    }
)


def _sanitize_program(program: dict[str, Any], *, base_url: str) -> None:
    normalize_program_layout(program)
    normalize_llm_rationales(program, default_source_url=base_url)


@click.command("research-node")
@click.argument("program_id")
@click.argument(
    "node",
    type=click.Choice(sorted(RESEARCH_NODES), case_sensitive=False),
)
@click.argument("query", required=False, default="")
@click.option(
    "--max-search-urls",
    default=10,
    type=int,
    show_default=True,
    help="Max distinct URLs to fetch evidence from.",
)
@click.option(
    "--evidence-budget-chars",
    default=0,
    type=int,
    show_default=True,
    help="Max combined characters of Markdown page excerpts; 0 = no cap.",
)
@click.option(
    "--max-llm-attempts",
    default=3,
    type=int,
    show_default=True,
    help="Schema-aware retries for the LLM response.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Run Tavily + LLM but do not write corpus/programs.json.",
)
def research_node_cmd(
    program_id: str,
    node: str,
    query: str,
    max_search_urls: int,
    evidence_budget_chars: int,
    max_llm_attempts: int,
    dry_run: bool,
) -> None:
    """Run a fresh Tavily search + LLM step for NODE on an existing PROGRAM_ID.

    Unlike reconsider-node (which re-fetches pages already cited in llm_rationales),
    this command issues new domain-scoped Tavily queries for the node and fetches
    fresh evidence. Useful when a node has no prior rationale URLs to draw from —
    most notably the `historical` node on programs ingested before that field existed.

    QUERY is an optional free-text hint appended to the Tavily search queries.
    """
    root = find_repo_root()
    load_env(root)
    provider, model, api_key, base_llm_url = require_llm_config()
    try:
        tavily_api_key()
    except RuntimeError as e:
        raise click.ClickException(str(e)) from e

    pid = (program_id or "").strip()
    if not pid:
        raise click.UsageError("program_id must be non-empty.")

    node_key = node.strip().lower()
    q = (query or "").strip()

    corpus = load_corpus(root)
    program = program_by_id(corpus, pid)
    if program is None:
        raise click.ClickException(f"Unknown program_id: {pid!r}")

    seed_url = str(program.get("base_url") or "").strip()
    if not seed_url:
        raise click.ClickException(f"Program {pid!r} has no base_url.")

    categories = load_categories(root)
    cat_json = categories_payload_for_prompt(categories)

    client = get_client(provider, api_key=api_key, model=model, base_url=base_llm_url)
    host = base_llm_url or "https://api.openai.com"

    cli_rule_line("=")
    cli_bracket_line(
        "rn",
        "setup",
        f"{pid} · {node_key} · {model} · {provider} · {cli_short_url(host)} · tavily",
    )
    cli_rule_line("-")

    def trace(msg: str) -> None:
        cli_bracket_line("rn", "fetch", msg, indent_tabs=1)

    def warn(msg: str) -> None:
        cli_bracket_line("rn", "fetch", msg, indent_tabs=1)

    evidence = gather_evidence_for_node(
        node_key,
        program,
        llm_client=client,
        repo_root=root,
        seed_url=seed_url,
        user_query=q,
        max_urls_total=max_search_urls,
        budget_chars=evidence_budget_chars,
        report=warn,
        trace=trace,
    )
    cli_bracket_line("rn", node_key, f"evidence {len(evidence)}c")

    raw = ""
    try:
        cli_bracket_line("rn", "json", f"LLM · {len(evidence)}c", indent_tabs=1)
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
        cli_bracket_line("rn", "json", f"fail schema: {e}")
        echo_llm_raw_and_parsed(
            e.raw,
            program,
            intro=f"research-node LLM output rejected by schema.",
            schema_errors=e.errors,
        )
        sys.exit(1)
    except (json.JSONDecodeError, ValueError, RuntimeError) as e:
        cli_bracket_line("rn", "json", f"fail: {e}")
        echo_llm_raw_and_parsed(raw, program, intro="research-node failure.")
        sys.exit(1)

    base = str(program.get("base_url") or "")
    _sanitize_program(program, base_url=base)
    bump_date_updated(program)

    enum_notes: list[str] = []
    errs = validate_corpus(
        root,
        corpus,
        category_repair_notes=enum_notes,
        repair_invalid_enums=True,
    )
    for line in enum_notes:
        cli_bracket_line("rn", "enum-repair", line, indent_tabs=1)
    if errs:
        echo_validation_errors(errs, intro="Corpus invalid after research-node.")
        sys.exit(1)

    if dry_run:
        cli_bracket_line("rn", "done", "dry-run OK")
        return

    write_corpus(root, corpus)
    cli_rule_line("=")
    cli_bracket_line("rn", "done", f"wrote {node_key} · {pid}")
