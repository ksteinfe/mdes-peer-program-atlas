# mdes-peer-program-atlas

Local-first umbrella repo for an MDes peer program comparator: canonical JSON corpus, Python CLI (`peer-atlas`), and a static HTML viewer.

## Layout

| Path | Purpose |
|------|---------|
| `corpus/programs.json` | Canonical corpus (`corpus_metadata` + `programs`) |
| `corpus/programs.backup.json` | Last backup before CLI writes |
| `categories_and_rules/*.json` | Category vocabularies (enums) plus optional `node_prompt_rules.json` (per-node keys, `extra_instructions` string arrays joined into `peer-atlas-cli/prompts/nodes/*.md`) |
| `corpus/programs.archive.*.json` | Optional dated full-corpus snapshots (written by `peer-atlas clear-programs`; gitignored) |
| `schemas/*.json` | JSON Schema for programs and patches |
| `peer-atlas-cli/` | Installable CLI and `peer-atlas-cli/prompts/` (LLM prompt templates) |
| `peer-atlas-viewer/` | Static viewer (split HTML/CSS/JS in dev) |

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

`clear-programs` archives the current `corpus/programs.json` to `corpus/programs.archive.<UTC>.json`, then sets `programs` to `[]` (keeps `corpus_metadata`). Use `-y` to skip the confirmation prompt.

`add-program` usage: `peer-atlas add-program BASE_URL PROGRAM_ID [optional query text]` — `BASE_URL` is stored on the program record and used for search seeding and evidence; `PROGRAM_ID` must be unique in the corpus (stable slug, e.g. `berkeley_mdes`).

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

Open `http://localhost:8080/`. Use **Load corpus** to pick `corpus/programs.json`, or **Load sample** (serves `dev/sample-corpus.json` when using the static server).

## Viewer (single-file publish)

From repo root (requires Node.js):

```bash
node peer-atlas-viewer/tools/bundle.mjs
```

Output: `peer-atlas-viewer/dist/atlas-viewer.html` (gitignored by default). Optional: pass path to corpus JSON to embed for offline sharing:

```bash
node peer-atlas-viewer/tools/bundle.mjs corpus/programs.json
```

## Patch workflow

1. Edit in the viewer (future) or export a patch scaffold.
2. `peer-atlas merge-patch exports/your_patch.json` applies validated changes by `program_id` and dot-path.

## `program_id`

Stable slug, typically `{institution_slug}_{program_slug}` (lowercase, underscores). Used for merge-patch, validate, and display.
