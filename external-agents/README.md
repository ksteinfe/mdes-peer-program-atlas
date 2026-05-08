# External agents

This directory holds **paired** artifacts for workflows where an **external agent** (no repository access) receives a **data snapshot** from the repo, then returns structured output (usually **patch JSON**).

## Layout

Each task lives in its **own subdirectory**. Inside that subdirectory you will always find:

1. **Instructions** — a Markdown file the operator pastes into (or attaches for) the external agent. It is self-contained: schemas, allowed values, and rules needed for that task only.
2. **Export script** — runnable from the repository root; writes a **`.txt`** file (JSON inside) under **`export-output/`** (gitignored) and prints only the **filename** to the console so you can open or attach that file for the agent.

Example:

```text
external-agents/
  README.md                          ← this file
  patch-identity-positioning/
    patch-identity-positioning.md    ← agent instructions
    export_snapshot.py               ← corpus → export-output/*.txt (JSON body; all programs for this task)
```

## Running an export script

From the **repository root** (where `corpus/programs.json` exists):

```bash
python external-agents/patch-identity-positioning/export_snapshot.py
```

This writes **one** timestamped **`.txt`** file under **`export-output/`** (ignored by git); the file content is **JSON** (pretty-printed). Prints its **basename** (e.g. `patch-identity-positioning_snapshot_20260508T155633Z.txt`). Each program includes **identity**, **positioning**, **`curriculum.curriculum_summary`** and **`curriculum.electives.summary`** (as a small `curriculum` object), and filtered **`llm_rationales`** for identity/positioning—see the task Markdown for the exact shape.

After changing `categories_and_rules/*.json` ids, regenerate **`peer-atlas-viewer/dev/viewer-categories.json`** with `node peer-atlas-viewer/tools/write-dev-catalog.mjs` and update any external-agent brief that inlines those ids (e.g. `patch-identity-positioning/patch-identity-positioning.md` §6) in the same change.
