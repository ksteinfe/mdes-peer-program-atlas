# mdes-peer-program-atlas

Local-first umbrella repo for an MDes peer program comparator: canonical JSON corpus, Python CLI (`peer-atlas`), and a static HTML viewer.

## Layout

| Path | Purpose |
|------|---------|
| `corpus/programs.json` | Canonical corpus (`corpus_metadata` + `programs`) |
| `categories_and_rules/*.json` | Category vocabularies (enums) plus optional `node_prompt_rules.json` (per-node keys, `extra_instructions` string arrays joined into `peer-atlas-cli/prompts/nodes/*.md`). After changing ids here, run `node peer-atlas-viewer/tools/write-dev-catalog.mjs` and update any external-agent briefs that inline those ids (e.g. `external-agents/patch-identity-positioning/patch-identity-positioning.md` §6). |
| `schemas/*.json` | JSON Schema for programs and patches |
| `peer-atlas-cli/` | Installable CLI and `peer-atlas-cli/prompts/` (LLM prompt templates) |
| `peer-atlas-viewer/` | Static viewer (split HTML/CSS/JS in dev) |
| `peer-atlas-viewer/icons/course-types/` | SVG (or later PNG) icons named `{id}.svg` matching `course_types.json` `id` values; used in the viewer and embedded as data URLs in the single-file bundle |
| `external-agents/` | Paired Markdown briefs + export scripts for agents without repo access (see `external-agents/README.md`) |
| `tools/` | Small automation scripts (e.g. batch `add-program` from a TSV) |

## CLI

From repo root:

```bash
cd peer-atlas-cli
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
peer-atlas --help
```

Commands: `validate`, `clear-programs`, `merge-patch`, `add-program`.

**Possible future commands** (not implemented today; prompt stubs live under `peer-atlas-cli/prompts/` if you wire them back in):

- **`refresh-program`** — re-fetch evidence URLs and merge an LLM-refreshed full program into the corpus.
- **`refine-program`** — apply a natural-language instruction via LLM with optional scoped Tavily evidence.
- **`reevaluate-categories`** — batch re-run category classification for paths tied to `categories_and_rules/*.json`.

`clear-programs` empties the `programs` array in `corpus/programs.json` (keeps `corpus_metadata`). Use `-y` to skip the confirmation prompt.

`add-program` usage: `peer-atlas add-program BASE_URL PROGRAM_ID [optional query text]` — `BASE_URL` is stored on the program record and used for search seeding and evidence; `PROGRAM_ID` must be unique in the corpus (stable slug, e.g. `berkeley_mdes`).

To queue many programs from a spreadsheet, use a **tab-separated** file with columns `base_url`, `program_id`, optional `query`, then run **`python tools/add-program-batch.py path/to/queue.tsv`** from the repo root (with `peer-atlas` on your `PATH`). See `python tools/add-program-batch.py --help`; use `--` to pass flags through to each `add-program` (e.g. `… queue.tsv -- --dry-run`).

Configure LLM (optional until you use LLM commands): copy `.env.example` to `.env` in the **repository root** and set `LLM_API_KEY`, `LLM_MODEL`, etc. For **`add-program`**, set **`TAVILY_API_KEY`**. Fetched pages are cached under `.peer-atlas/url-cache/` as JSON (`body`, `body_markdown`, char counts). Playwright Chromium is tried first, then httpx — run **`playwright install chromium`** once after install. See **`peer-atlas-cli/README.md`** for the evidence pipeline, domain-scoped Tavily, and **`PEER_ATLAS_HTML_MARKDOWN_LLM_INPUT_CHARS`**. **`PEER_ATLAS_FETCH_COOKIE`** is sent on both paths; optional **`PEER_ATLAS_PLAYWRIGHT_HEADED=1`** runs a visible browser for debugging.

```bash
peer-atlas validate
peer-atlas merge-patch path/to/patch.json
```

## Viewer (development)

Serve the viewer folder with a static server (avoids `file://` issues with modules and `fetch`):

```bash
python -m http.server 8080 --directory peer-atlas-viewer
```

Open `http://localhost:8080/`. Use **Load corpus** to pick `corpus/programs.json`, or **Load sample** (serves `dev/sample-corpus.json`). Category labels for dev builds come from `dev/viewer-categories.json` (mirrors `categories_and_rules/*.json`); regenerate after changing category ids or labels:

```bash
node peer-atlas-viewer/tools/write-dev-catalog.mjs
node peer-atlas-viewer/tools/slim-corpus-for-viewer.mjs corpus/programs.json peer-atlas-viewer/dev/sample-corpus.json
```

If you add **positioning** or **host** vocabulary entries, also update **`external-agents/patch-identity-positioning/patch-identity-positioning.md`** §6 so external-agent instructions stay in sync.

The **Load corpus** / **Load sample** controls live inside `<!-- peer-atlas:bundle-remove:start -->` … `<!-- peer-atlas:bundle-remove:end -->` in `peer-atlas-viewer/index.html`; the dist bundle strips that region (see **Viewer (single-file publish / dist)** below).

## Viewer (single-file publish / dist)

From repo root (requires Node.js). This writes **`peer-atlas-viewer/dist/atlas-viewer.html`** (often gitignored): one file with **inlined CSS and JS**, optional **embedded slim corpus + category enums**, **course-type SVGs** from `peer-atlas-viewer/icons/course-types/` as base64 in a JSON script (offline-safe icons), **minified** where safe (HTML inter-tag whitespace and comments removed; CSS comments and extra whitespace collapsed; module script gets conservative blank-line / trailing-space trimming only—no full JS minify to avoid breaking the bundle without extra tooling).

**Dev-only UI is stripped from dist:** anything between `<!-- peer-atlas:bundle-remove:start -->` and `<!-- peer-atlas:bundle-remove:end -->` in `peer-atlas-viewer/index.html` is omitted (today that is **Load corpus…**, the hidden file input, and **Load sample**). The shipped page is meant to open with data already embedded or loaded another way you add later.

**Typical production build** (embed canonical corpus + rules-derived labels):

```bash
node peer-atlas-viewer/tools/bundle.mjs X:\GitHub\mdes-peer-program-atlas\corpus\programs.json
```

Relative path from repo root also works:

```bash
node peer-atlas-viewer/tools/bundle.mjs corpus/programs.json
```

Omit the corpus argument to produce a single HTML file **without** embedded JSON blobs (viewer still runs; users would need another mechanism to supply data, since the dist toolbar no longer includes load buttons):

```bash
node peer-atlas-viewer/tools/bundle.mjs
```

## Patch workflow

1. Open a program in the viewer, use **Edit**, then **Export patch for this program** to download a patch JSON.
2. `peer-atlas merge-patch exports/your_patch.json` applies validated changes by `program_id` and dot-path. Paths that do not yet exist on a program may require `peer-atlas merge-patch --allow-new-paths`.

## `program_id`

Stable slug, typically `{institution_slug}_{program_slug}` (lowercase, underscores). Used for merge-patch, validate, and display.
