"""classify-cip — assign identity.cip_code via a single LLM call (no web search)."""

from __future__ import annotations

import json
import sys

import click

from peer_atlas_cli.categories import categories_payload_for_prompt, load_categories
from peer_atlas_cli.cli_progress import cli_bracket_line, cli_rule_line, cli_short_url
from peer_atlas_cli.config import load_env, require_llm_config
from peer_atlas_cli.corpus_io import load_corpus, program_by_id, write_corpus
from peer_atlas_cli.program_dates import bump_date_updated
from peer_atlas_cli.llm_client import get_client
from peer_atlas_cli.llm_nodes import LLMSchemaValidationError, run_cip_code_step
from peer_atlas_cli.llm_reporting import echo_llm_raw_and_parsed, echo_validation_errors
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.schema_validation import validate_corpus


@click.command("classify-cip")
@click.argument("program_id")
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
    help="Run LLM but do not write corpus/programs.json.",
)
def classify_cip_cmd(program_id: str, max_llm_attempts: int, dry_run: bool) -> None:
    """Assign identity.cip_code for PROGRAM_ID via a single LLM classification call.

    Uses only the program's existing descriptive text (identity, positioning summary,
    curriculum summary) and the curated cip_codes category list. No web search or
    Tavily required.
    """
    root = find_repo_root()
    load_env(root)
    provider, model, api_key, base_llm_url = require_llm_config()

    pid = (program_id or "").strip()
    if not pid:
        raise click.UsageError("program_id must be non-empty.")

    corpus = load_corpus(root)
    program = program_by_id(corpus, pid)
    if program is None:
        raise click.ClickException(f"Unknown program_id: {pid!r}")

    categories = load_categories(root)
    cat_json = categories_payload_for_prompt(categories)

    client = get_client(provider, api_key=api_key, model=model, base_url=base_llm_url)
    host = base_llm_url or "https://api.openai.com"

    cli_rule_line("=")
    cli_bracket_line("cip", "setup", f"{pid} · {model} · {provider} · {cli_short_url(host)}")
    cli_rule_line("-")

    raw = ""
    try:
        cli_bracket_line("cip", "classify", "LLM · cip_code classification", indent_tabs=1)
        raw = run_cip_code_step(
            client=client,
            program=program,
            categories_json=cat_json,
            repo_root=root,
            max_llm_attempts=max_llm_attempts,
        )
        if not raw:
            ident = program.get("identity") or {}
            if not ident.get("ipeds_unitid"):
                cli_bracket_line("cip", "skip", "no ipeds_unitid — cip_code set to null")
            else:
                cli_bracket_line("cip", "skip", f"cip_code already set: {ident.get('cip_code')!r}")
    except LLMSchemaValidationError as e:
        cli_bracket_line("cip", "LLM", f"fail schema: {e}")
        echo_llm_raw_and_parsed(
            e.raw, program,
            intro="classify-cip LLM output rejected by schema.",
            schema_errors=e.errors,
        )
        sys.exit(1)
    except (json.JSONDecodeError, ValueError, RuntimeError) as e:
        cli_bracket_line("cip", "LLM", f"fail: {e}")
        echo_llm_raw_and_parsed(raw, program, intro="classify-cip failure.")
        sys.exit(1)

    ident = program.get("identity") or {}
    if raw:
        cli_bracket_line("cip", "result", f"cip_code = {ident.get('cip_code')!r}")

    if not raw:
        cli_rule_line("=")
        cli_bracket_line("cip", "done", f"skipped · {pid}")
        return

    bump_date_updated(program)

    enum_notes: list[str] = []
    errs = validate_corpus(
        root, corpus,
        category_repair_notes=enum_notes,
        repair_invalid_enums=True,
    )
    for line in enum_notes:
        cli_bracket_line("cip", "enum-repair", line, indent_tabs=1)
    if errs:
        echo_validation_errors(errs, intro="Corpus invalid after classify-cip.")
        sys.exit(1)

    if dry_run:
        cli_bracket_line("cip", "done", "dry-run OK")
        return

    write_corpus(root, corpus)
    cli_rule_line("=")
    cli_bracket_line("cip", "done", f"wrote cip_code · {pid}")
