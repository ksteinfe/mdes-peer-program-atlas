# peer-atlas-cli

Install from repository root:

```bash
pip install -e "./peer-atlas-cli[dev]"
```

Entry point: `peer-atlas`. `clear-programs` archives `corpus/programs.json` to `corpus/programs.archive.<UTC>.json` then empties the `programs` array (keeps `corpus_metadata`); use `-y` to skip confirmation. `add-program BASE_URL PROGRAM_ID [query]` uses **Tavily** search plus cached HTTP fetches, then one LLM call per top-level corpus node (plus per–core-course patches). Set `TAVILY_API_KEY` in repo-root `.env`.

**Curriculum path:** evidence for `curriculum_overview` is limited to the **registrable domain** of `BASE_URL` (e.g. `ischool.berkeley.edu` → `berkeley.edu` via Tavily `include_domains`). For each queued URL the CLI **fetches the full page** (up to `--curriculum-max-chars-per-url`, 0 = very large cap), runs a **separate prose LLM** to extract dense curriculum-related text, **concatenates** those blocks into `curriculum.evidence_curriculum_summary`, then runs the **JSON overview** LLM on that mash plus minimal program context (not the full program JSON). Defaults: `--curriculum-max-urls` 4. The `--curriculum-budget-chars` flag is unused for this node (kept for compatibility). Other nodes still use `--max-search-urls` (default 8) and a fixed per-node budget.

`reconsider-node PROGRAM_ID NODE INSTRUCTION...` re-runs one ingest node for an existing program: it sends the **current** program JSON, your **instruction** text, matching **`llm_rationales`** rows (by `feature` prefix for that node), **fetched** text for those rows’ `source_url` values (same cache as ingest), and the same **node prompt + `node_prompt_rules`** as `add-program`. The model may return new **`llm_rationales`** objects; those are **appended** to the corpus program (existing rationales stay). Use `curriculum_overview` when you want the overview-style curriculum prompt (LLM still returns a top-level `curriculum` object); the existing **`curriculum.evidence_curriculum_summary`** is preserved when present. Options: `--dry-run`, `--max-chars-per-url`, `--max-total-chars`, `--max-llm-attempts`.

**Possible future commands** (not registered in the CLI today): `refresh-program`, `refine-program`, `reevaluate-categories` — see repo root `README.md` for a short description; related prompts remain under `prompts/` if you re-add them to `main.py`.

**Page fetch (Playwright):** the CLI tries **headless Chromium** first, then falls back to **httpx** if Playwright is missing or returns a non-200 response. After `pip install`, run **`playwright install chromium`** once so Chromium is available. Optional: `PEER_ATLAS_PLAYWRIGHT_HEADED=1` for a visible browser; `PEER_ATLAS_FETCH_COOKIE` is sent on Playwright and httpx requests.

**Ingest LLM:** each node and each curriculum course patch retries up to **3** times if the merged program fails JSON Schema, feeding schema errors back to the model. On failure, stderr shows a short summary; set **`PEER_ATLAS_LLM_DEBUG=1`** for full raw + parsed dumps. For **`curriculum_overview`** per-source extracts, stderr always logs each extract’s **full assistant reply** and a **preview** of the user message sent to the model (first 12k chars); set **`PEER_ATLAS_CURRICULUM_EXTRACT_DEBUG=1`** to print the **entire** user message as well.

During evidence gathering, stderr lists how many URLs are **queued** for the node (after Tavily + dedupe), then each page actually retrieved as **`fetch: cache <url>`** (disk TTL cache) or **`fetch: network <url>`** (live Playwright/httpx). A **cumulative character budget** per node can stop the loop early, so you may see fewer `fetch:` lines than queued URLs; a follow-up line explains when remaining URLs were skipped.