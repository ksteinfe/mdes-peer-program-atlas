# peer-atlas-cli

Install from repository root:

```bash
pip install -e "./peer-atlas-cli[dev]"
```

Entry point: `peer-atlas`. `clear-programs` archives `corpus/programs.json` to `corpus/programs.archive.<UTC>.json` then empties the `programs` array (keeps `corpus_metadata`); use `-y` to skip confirmation. `add-program BASE_URL PROGRAM_ID [query]` uses **Tavily** search plus cached HTTP fetches, then one LLM call per top-level corpus node (plus per–core-course patches). Set `TAVILY_API_KEY` in repo-root `.env`.

**Page fetch (Playwright):** the CLI tries **headless Chromium** first, then falls back to **httpx** if Playwright is missing or returns a non-200 response. After `pip install`, run **`playwright install chromium`** once so Chromium is available. Optional: `PEER_ATLAS_PLAYWRIGHT_HEADED=1` for a visible browser; `PEER_ATLAS_FETCH_COOKIE` is sent on Playwright and httpx requests.

**Ingest LLM:** each node and each curriculum course patch retries up to **3** times if the merged program fails JSON Schema, feeding schema errors back to the model. On failure, stderr shows a short summary; set **`PEER_ATLAS_LLM_DEBUG=1`** for full raw + parsed dumps.

During evidence gathering, stderr lists **Tavily/seed URLs** to fetch, then each page as **`fetch: cache <url>`** (disk TTL cache) or **`fetch: network <url>`** (live Playwright/httpx).