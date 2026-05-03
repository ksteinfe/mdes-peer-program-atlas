"""Build evidence payloads for ``reconsider-node`` (rationales + fetched sources)."""

from __future__ import annotations

import json
import pathlib
from collections.abc import Callable
from typing import Any

from peer_atlas_cli.retrieval.fetch_cached import fetch_url_text_cached
from peer_atlas_cli.retrieval.url_normalize import normalize_url

# Nodes the user may pass on the CLI (includes overview-style curriculum pass).
RECONSIDER_NODES: frozenset[str] = frozenset(
    {
        "positioning",
        "duration",
        "degree_cost",
        "curriculum",
        "curriculum_overview",
        "identity",
        "verification",
    }
)


def _feature_matches_node(node: str, feature: str) -> bool:
    f = (feature or "").strip()
    if not f:
        return False
    if node == "curriculum_overview":
        return f == "curriculum" or f.startswith("curriculum.")
    return f == node or f.startswith(f"{node}.")


def rationales_for_node(node: str, program: dict[str, Any]) -> list[dict[str, Any]]:
    """Return ``llm_rationales`` entries whose ``feature`` belongs to this node."""
    raw = program.get("llm_rationales")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        feat = item.get("feature")
        if feat is None and "derived_feature" in item:
            feat = item.get("derived_feature")
        if _feature_matches_node(node, str(feat or "")):
            out.append(dict(item))
    return out


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        n = normalize_url(u)
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(u)
    return out


def fetch_rationale_source_pages(
    repo_root: pathlib.Path,
    rationales: list[dict[str, Any]],
    *,
    max_chars_per_url: int,
    max_total_chars: int,
    report: Callable[[str], None] | None = None,
    trace: Callable[[str], None] | None = None,
) -> str:
    """
    Fetch ``source_url`` from each rationale (deduped), return one markdown-ish block.
    """
    urls: list[str] = []
    for item in rationales:
        if not isinstance(item, dict):
            continue
        u = str(item.get("source_url") or "").strip()
        if u.startswith(("http://", "https://")):
            urls.append(u)
    urls = _dedupe_urls(urls)
    parts: list[str] = []
    used = 0
    for url in urls:
        if used >= max_total_chars:
            if trace is not None:
                trace(
                    f"reconsider: skipping remaining rationale URL(s) "
                    f"(total char budget {max_total_chars} reached)"
                )
            break
        try:
            text = fetch_url_text_cached(
                url,
                repo_root=repo_root,
                max_chars=max_chars_per_url,
                report=report,
                trace=trace,
            )
        except Exception as e:
            text = f"(fetch failed: {e})"
            if report is not None:
                report(f"Rationale URL fetch failed: {url}\n  {e}")
        header = f"\n\n=== RATIONALE SOURCE_URL: {url} ===\n"
        chunk = header + text
        if used + len(chunk) > max_total_chars:
            chunk = chunk[: max(0, max_total_chars - used)]
        parts.append(chunk)
        used += len(chunk)
    return "".join(parts) if parts else "(no rationale source_url values to fetch)\n"


def build_reconsider_evidence(
    *,
    user_instruction: str,
    rationales: list[dict[str, Any]],
    fetched_pages: str,
    primary_response_key: str,
) -> str:
    """Single EVIDENCE string passed into the normal node prompt templates."""
    instr = (user_instruction or "").strip()
    if not instr:
        instr = "(no instruction text provided)"
    pk = (primary_response_key or "").strip() or "node"
    return (
        "## Human instruction (prioritize strongly)\n"
        f"{instr}\n\n"
        "## Relevant llm_rationales from corpus (subset for this node)\n"
        f"{json.dumps(rationales, indent=2, ensure_ascii=False)}\n\n"
        "## Fetched page text for those rationale source_url values\n"
        f"{fetched_pages}\n"
        "## Reconsideration output (required)\n"
        f"- Return a JSON object whose **only** required top-level key is **`\"{pk}\"`** (the updated node subtree), matching the same shape as normal ingest for this step.\n"
        "- You **may** also return optional top-level **`\"llm_rationales\"`** (array) and/or **`\"sources\"`** (array), same rules as ingest.\n"
        "- For each new rationale object use **exactly** these string keys: **`feature`**, **`source_url`**, **`note`**. "
        "Set **`feature`** to the dot path of the field the note supports (e.g. `positioning.positioning_tags`, `degree_cost.comparison_cost_usd`). "
        "New **`llm_rationales`** entries are **appended** to the program record (existing rationales above are not removed); add at least one new row when your edits or the human instruction warrant an audit trail.\n"
    )
