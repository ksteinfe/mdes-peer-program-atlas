"""CLI: clear URL cache entry (if any), re-fetch, run HTML→markdown evidence path."""

from __future__ import annotations

import click

from peer_atlas_cli.config import require_llm_config
from peer_atlas_cli.llm_client import get_client
from peer_atlas_cli.repo_root import find_repo_root
from peer_atlas_cli.retrieval.fetch_cached import fetch_url_text_cached
from peer_atlas_cli.retrieval.url_cache import cache_dir_for_repo, clear_cache_entry_for_url


@click.command("test-evidence-url")
@click.argument("url")
@click.option(
    "--max-chars",
    default=120_000,
    type=int,
    show_default=True,
    help="Per-URL character cap passed to the fetch layer (same coalesce rules as ingest).",
)
@click.option(
    "--timeout",
    default=30.0,
    type=float,
    show_default=True,
    help="HTTP / Playwright timeout in seconds for the live fetch.",
)
def test_evidence_url_cmd(url: str, max_chars: int, timeout: float) -> None:
    """
    Clear the disk cache for URL (if present), download the page again, simplify HTML,
    optionally run the main-body Markdown LLM (unless ``PEER_ATLAS_SKIP_HTML_MARKDOWN_LLM``),
    write the cache JSON, and print the same string ingest would use as evidence (stdout).

    Progress and warnings go to stderr so you can redirect stdout to a file.
    """
    u = (url or "").strip()
    if not u.startswith(("http://", "https://")):
        raise click.UsageError("url must start with http:// or https://")

    root = find_repo_root()
    provider, model, api_key, base_llm_url = require_llm_config()
    client = get_client(provider, api_key=api_key, model=model, base_url=base_llm_url)

    cache_dir = cache_dir_for_repo(root)
    removed = clear_cache_entry_for_url(cache_dir, u)
    if removed:
        click.echo(f"Removed {removed} cache file(s); forcing network fetch.", err=True)
    else:
        click.echo("No on-disk cache entry for this URL (fetching from network).", err=True)

    click.echo(f"model={model!r} provider={provider!r}", err=True)
    text = fetch_url_text_cached(
        u,
        repo_root=root,
        timeout=timeout,
        max_chars=max_chars,
        llm_client=client,
        report=lambda m: click.echo(m, err=True),
        trace=lambda m: click.echo(m, err=True),
    )
    click.echo(text)
