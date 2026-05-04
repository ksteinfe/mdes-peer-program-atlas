# peer-atlas-cli

Install from repository root:

```bash
pip install -e "./peer-atlas-cli[dev]"
```

Entry point: `peer-atlas`. `clear-programs` empties the `programs` array in `corpus/programs.json` (keeps `corpus_metadata`); use `-y` to skip confirmation.

**`sources` (per program):** required array of normalized URL strings — an inventory of every ``url`` stored in a JSON file under the repo url-cache (``.peer-atlas/url-cache`` or ``PEER_ATLAS_FETCH_CACHE_DIR``) whose **registrable domain** matches the program's ``base_url`` (same rule as Tavily host scoping in ``host_scope.py``), **plus** any cache file whose **filename** contains the program's registrable domain or hostname (so pages cached under a path-style filename still attach). Multiple programs at the same institution therefore often share overlapping ``sources`` lists. Refresh after fetches with **`peer-atlas refresh-sources`** (optional **`--dry-run`**); **`add-program`** also refreshes ``sources`` before each corpus validation pass.

**Category enums (`INVALID`):** Each vocabulary JSON under ``categories_and_rules/`` includes an ``INVALID`` id. During **`add-program`**, **`reconsider-node`**, **`merge-patch`**, **`refresh-sources`**, and **`remove-last-program`**, unknown positioning tags / course types / host models / duration / unit system / sequencedness / verification values are **replaced in memory** with ``INVALID`` (and stderr lines log the bad value). ``design_studio`` rows still get ``secondary_type`` cleared to ``null``. **`peer-atlas validate`** does **not** apply that repair (it checks the JSON as loaded).

`add-program BASE_URL PROGRAM_ID [query]` uses **Tavily** (scoped to the registrable domain of `BASE_URL`) plus cached fetches, then LLM steps per ingest node (plus per–core-course patches). Set `TAVILY_API_KEY` in repo-root `.env`.

**Tavily query text** is composed from a seed-page LLM pass (`atlas_search_context`), identity fallbacks, optional CLI `query`, and templates in [`categories_and_rules/tavily_search_guidance.json`](../categories_and_rules/tavily_search_guidance.json). See [docs/tavily-query-composition.md](docs/tavily-query-composition.md).

**Evidence gathering pipeline** (queries → Tavily → URLs → raw HTML → simplified HTML → **required** main-body Markdown LLM → URL cache) does **not** truncate downloaded HTML. Cache JSON includes `body`, `body_markdown`, `body_chars`, and `body_markdown_chars`. The html→Markdown model receives at most **`PEER_ATLAS_HTML_MARKDOWN_LLM_INPUT_CHARS`** characters of simplified HTML; if the page is larger, stderr reports that the input was truncated **for that model only**. Tavily hits that look like PDF/DOC/XLS/etc. are dropped.

**Curriculum path:** `curriculum_overview` uses `--curriculum-max-urls` (default 4) domain-scoped URLs, **full** Markdown per page, a **prose** LLM per source (`curriculum_source_extract`), then a **JSON** overview LLM on the concatenated mash (not stored on the program). Per `core_courses[i]` row: Tavily + Markdown fetches (domain-scoped when `BASE_URL` is passed as `seed_url`), then `curriculum_course_patch`.

**CLI knobs:** `--max-search-urls` (default 8), `--curriculum-max-urls` (default 4), **`--evidence-budget-chars`** (default 0 = unlimited) caps the **combined Markdown** (plus `=== SOURCE URL ===` headers) passed into a single node or per-course evidence string — not applied inside the fetch pipeline.

`test-evidence-url URL` clears on-disk cache for **URL**, re-runs the full pipeline, writes cache (with char counts), prints Markdown to **stdout**. Option: `--timeout`.

`reconsider-node PROGRAM_ID NODE INSTRUCTION...` re-runs one ingest node: same prompts as ingest, plus instruction, rationales, and fetched Markdown for rationale `source_url` values (PDF-style URLs skipped). Options: `--dry-run`, `--max-total-chars` (default 2_000_000 for the combined rationale-fetch block), `--max-llm-attempts`.

**Page fetch (Playwright):** headless Chromium first, then **httpx** fallback. After `pip install`, run **`playwright install chromium`** once. After **`domcontentloaded`**, the CLI waits for a **content-region** selector (see `html_text.CONTENT_REGION_SELECTORS`), **text-stability** sampling, optional **scroll** (`PEER_ATLAS_PLAYWRIGHT_SCROLL_MAIN=0` to disable), then **`page.content()`** (full HTML, not truncated). Optional: `PEER_ATLAS_PLAYWRIGHT_HEADED=1`, `PEER_ATLAS_FETCH_COOKIE`, `PEER_ATLAS_PLAYWRIGHT_POST_LOAD_SECONDS`, `PEER_ATLAS_PLAYWRIGHT_STABLE_INTERVAL_MS`.

**Ingest LLM:** schema-aware retries (default 3). Set **`PEER_ATLAS_LLM_DEBUG=1`** for full dumps. Transcripts under **`.peer-atlas/llm-last-session/`** (cleared each `peer-atlas` run).

During evidence assembly, stderr shows **`fetch: cache`** vs **`fetch: network`**. With a positive **`--evidence-budget-chars`**, fetching may stop early once the Markdown bundle would exceed the budget.
