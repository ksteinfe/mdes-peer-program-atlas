# Tavily query composition

This document describes how the CLI builds **plain-text search strings** sent to the Tavily API, how those relate to the **CLI `base_url`** (domain scoping), and where to change behavior without editing Python.

## Order of operations (`add-program`)

1. **`apply_identity_fallbacks`** — Fills missing `identity.institution_name` / `program_name` from the hostname and URL path (no LLM).
2. **`search_context` stage** — Fetches Markdown for the CLI **`base_url`**, then runs a small LLM (`search_context_from_seed`) that may set draft-only **`atlas_search_context`** (`official_program_label`, `short_institution`, `degree_subject_keywords`). This improves Tavily labels before any evidence node runs.
3. **Per ingest node** — For each node in `INGEST_MAIN_NODES`, the CLI builds one or more **query strings**, calls Tavily (with **`include_domains`** derived from the registrable domain of `base_url` when scoped), ranks hits, caps URLs, then fetches pages.

`atlas_search_context` and `atlas_ingest` are **removed** before publish (`strip_atlas_ingest`).

## What each layer controls

| Layer | Role |
|--------|------|
| [`categories_and_rules/tavily_search_guidance.json`](../../categories_and_rules/tavily_search_guidance.json) | Templates and per-node query patterns (`{label}`, `{institution}`, …). |
| [`peer_atlas_cli/retrieval/query_builders.py`](../peer_atlas_cli/retrieval/query_builders.py) | Resolves `{label}` (search context → identity → CLI query → fallback), formats templates (including identity `site:` skip when `seed_url` empty). |
| [`peer_atlas_cli/retrieval/evidence_gathering_pipeline.py`](../peer_atlas_cli/retrieval/evidence_gathering_pipeline.py) | `search_urls_for_evidence`: Tavily **`include_domains`**, PDF/office URL drop. |
| [`peer_atlas_cli/retrieval/tavily_search.py`](../peer_atlas_cli/retrieval/tavily_search.py) | HTTP payload: **`max_results`** clamped to 1–20. |
| [`peer_atlas_cli/retrieval/evidence_bundle.py`](../peer_atlas_cli/retrieval/evidence_bundle.py) | Merges hits from all queries per node, ranks, **`max_urls_total`**, optional Markdown **`budget_chars`**. |

## `{label}` resolution

The primary phrase **`{label}`** in templates is chosen in order:

1. `atlas_search_context.official_program_label` (non-empty), from the seed-page LLM.
2. `identity.institution_name` + `identity.program_name` (joined).
3. CLI optional **`query`** argument to `add-program`.
4. `composition.fallback_label` from the JSON guidance (default: `graduate design program`).

## CLI arguments

- **`BASE_URL`** — Seed for fetches and registrable domain for Tavily scoping (not always repeated inside the query text).
- **`[query]`** — Fallback human text for `{label}` when identity and search context are weak.

See `peer-atlas add-program --help` for **`--max-search-urls`**, **`--curriculum-max-urls`**, and **`--evidence-budget-chars`**.
