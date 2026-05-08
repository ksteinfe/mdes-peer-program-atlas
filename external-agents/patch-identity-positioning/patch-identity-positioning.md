# Task: Propose corpus patches (identity and positioning only)

You are an external agent **without access to this repository’s files**. Everything required to produce valid **patch JSON** for the allowed sections is below. Your operator supplies a **single JSON snapshot** of current **identity**, **positioning**, and **read-only curriculum text snippets** for **all programs** in the corpus (see §2), plus **natural-language instructions** for what to change. You **must not** use web search or browse the internet; apply updates **only** from what the operator provides in the prompt (snapshot + instructions). Your deliverable is **patch JSON** that a human or automated job will apply with the project’s `peer-atlas merge-patch` command.

---

## 1. Scope of this task

You may propose changes **only** under these dot-path prefixes on an existing program:

| Prefix | Meaning |
|--------|---------|
| `identity.` | Institution, program names, credential, degree type label, host units, host academic model, location |
| `positioning.` | Positioning summary text; controlled positioning tags |

**Out of scope (do not emit `path` values under these or for these keys):**

- `degree_cost.*`, `duration.*`, **`curriculum.*`** (including `curriculum.curriculum_summary` and `curriculum.electives.summary`—those appear in the snapshot **for context only**; do **not** patch them in this task), `verification.*`, `sources`, `base_url`, `date_added`, `date_updated`
- **`program_id`** — treat it as the stable key you are given; do not rename programs here
- **`llm_rationales`** — the snapshot may include related rows **for your context only**; do **not** add, delete, or edit rationale entries via patches in this task

If the operator asks for something outside scope, explain the limitation in **`patch_metadata.notes`** and **omit** it from `changes`.

---

## 2. What you are given

Your operator must provide:

1. A **snapshot file** produced by the paired repo script `export_snapshot.py` (no arguments). The script writes under the repo’s **`export-output/`** directory (not tracked in git) a timestamped **`.txt`** file (e.g. `patch-identity-positioning_snapshot_20260508T155633Z.txt`) whose **contents are JSON**—one document with **every program**. The script prints that **filename** to the console. Top-level shape:

| Key | Content |
|-----|---------|
| `snapshot_metadata` | `task`, `exported_at`, `corpus_file`, `program_count`, `output_file` (relative path) — traceability |
| `programs` | Array of per-program objects (see below) |

Each element of **`programs`** has:

| Key | Content |
|-----|---------|
| `program_id` | Stable id string for that program |
| `identity` | Object — current `identity` block from the corpus |
| `positioning` | Object — current `positioning` block from the corpus |
| `curriculum` | Object — **read-only** context: `curriculum_summary` (string) and nested `electives.summary` (string). Mirrors `curriculum.curriculum_summary` and `curriculum.electives.summary` in the corpus; empty strings if missing. **Do not emit patches** under `curriculum.*` in this task |
| `llm_rationales` | Array — **only** rationale objects whose `feature` is a dot path starting with `identity.` or `positioning.` (ingest provenance). Read-only context; **do not patch** rationales |

2. **Operator instructions** in natural language. These may reference **one or many** `program_id` values (e.g. “for `berkeley_mdes`, …” or “normalize location_label for all UC programs listed below: …”). Apply only what the operator specifies.

For each change you emit, set **`program_id`** on that change object to the program you are editing, and set **`old_value`** from **that program’s** entry inside `programs` in the snapshot (match `program_id` first, then read `identity` / `positioning` as needed). The **`curriculum`** object in the snapshot is for alignment context only (e.g. keeping positioning text consistent with curriculum prose); **`old_value` / `new_value` for patches** still come only from **`identity.*`** and **`positioning.*`** fields. Derive **`new_value`** **only** from the operator’s instructions and those patchable objects—**no external sources**.

---

## 3. Patch document shape (complete rules)

Output a single JSON **object** (not an array). No extra top-level keys. No extra keys on `patch_metadata` or on each change object beyond those listed.

### 3.1 Top level

| Key | Required | Type | Rules |
|-----|----------|------|--------|
| `patch_metadata` | yes | object | See §3.2 |
| `changes` | yes | array | Each item: see §3.3 |

### 3.2 `patch_metadata`

| Key | Required | Type | Rules |
|-----|----------|------|--------|
| `created_at` | yes | string | ISO date recommended, e.g. `2026-05-08` |
| `created_by` | yes | string | Agent name, human operator, or `""` if unknown |
| `source_corpus_name` | yes | string | Use exactly: `MDes Peer Program Comparator Corpus` unless your operator specifies otherwise |
| `notes` | no | string | Batch-level summary; if the operator’s request was ambiguous or partially out of scope, say so here |

### 3.3 Each element of `changes`

| Key | Required | Type | Rules |
|-----|----------|------|--------|
| `program_id` | yes | string | Must match a `program_id` present in the snapshot’s `programs` array |
| `path` | yes | string | Non-empty **dot path** (see §5) |
| `old_value` | yes | any JSON | Must **exactly match** the current corpus value at `path` when the patch is applied (§4). Use JSON `null` for missing or null fields. |
| `new_value` | yes | any JSON | Value to set at `path` after a successful `old_value` check |
| `notes` | no | string | Optional short note (e.g. quoting the operator instruction you applied) |

**`path` format:** segments separated by `.` (period). Examples: `identity.program_name`, `positioning.positioning_summary`, `identity.host_academic_units`.

**Arrays:** To replace an entire array (e.g. `positioning.positioning_tags`), use that path once with `old_value` / `new_value` as the **full JSON arrays**.

---

## 4. `old_value` and apply semantics (critical)

Patch tooling:

1. Loads the program by **`program_id`**.
2. Reads the current value at **`path`** (missing path → current value treated as **`null`**).
3. Compares to **`old_value`** with **deep JSON equality** (`1` ≠ `"1"`; match the snapshot literally).
4. On any mismatch, **aborts** the whole merge.
5. Otherwise writes **`new_value`** to **`path`**.

Always copy **`old_value`** from the **correct program** in the snapshot’s **`programs`** array (same `program_id` as on the change). Do **not** rely on `--skip-old-check` (operator may refuse to use it).

---

## 5. Allowed paths and field definitions

### 5.1 `identity` (object)

| `path` | Type | Allowed values / notes |
|--------|------|-------------------------|
| `identity.institution_name` | string | Free text |
| `identity.program_name` | string | Free text |
| `identity.credential_name` | string | Free text |
| `identity.degree_type` | string | Free text (e.g. `MDes`); not a fixed enum in corpus validation |
| `identity.host_academic_units` | array of strings | Free text per element |
| `identity.host_academic_model` | string | **Must be exactly one id** from §6.1 |
| `identity.location_label` | string | Free text |

### 5.2 `positioning` (object)

| `path` | Type | Allowed values / notes |
|--------|------|-------------------------|
| `positioning.positioning_summary` | string | Free text |
| `positioning.positioning_tags` | array of strings | **Unique** entries; each **must** be an id from §6.2 |

---

## 6. Controlled vocabularies (complete id lists)

### 6.1 `identity.host_academic_model`

| `id` | Label (for your disambiguation) |
|------|----------------------------------|
| `INVALID` | Invalid / unknown |
| `design_engineering_business_shared_hosted` | co-hosted by design + engineering + business units |
| `engineering_design_shared_hosted` | co-hosted by engineering + design units |
| `engineering_arts_shared_hosted` | co-hosted by engineering + fine arts units |
| `engineering_business_shared_hosted` | co-hosted by engineering + business units |
| `design_business_shared_hosted` | co-hosted by design + business units |
| `engineering_hosted` | hosted in an engineering unit |
| `design_hosted` | hosted in a design unit |
| `arts_hosted` | hosted in an arts / humanities unit |
| `business_hosted` | hosted in a business / management unit |
| `computing_hosted` | hosted in CS / information technology unit |
| `unknown` | Unknown |

### 6.2 `positioning.positioning_tags` (each array element)

| `id` | Label (for your disambiguation) |
|------|----------------------------------|
| `INVALID` | Invalid / unknown — avoid unless the operator explicitly cannot choose a better id |
| `interdisciplinary` | Interdisciplinary |
| `mecheng_adjacent` | Mech Eng Adjacent |
| `hci_adjacent` | HCI Adjacent |
| `ui_ux` | UI/UX |
| `fine_arts_adjacent` | Fine Arts Adjacent |
| `humanities_adjacent` | Humanities Adjacent |
| `architecture_adjacent` | Architecture Adjacent |
| `public_policy_adjacent` | Public Policy Adjacent |
| `media_adjacent` | Media Adjacent |
| `entrepreneurship_adjacent` | Entrepreneurship Adjacent |
| `professional` | Professional |
| `research` | Research |
| `social_impact` | Social Impact |
| `physical_making` | Physical Making |
| `digital` | Digital Making |
| `emerging_technologies` | Emerging Technologies |
| `critical_speculative_design` | Critical / Speculative Design |
| `interaction_design` | Interaction Design |
| `industrial_product_design` | Industrial / Product Design |
| `service_design` | Service design |
| `strategic_design` | Strategic design |
| `sustainability` | Sustainability |
| `systems_thinking` | Systems thinking |
| `human_centered` | Human-centered design |

**Tag rules:** no duplicates in one array; omit tags the operator did not ask for.

**Maintainers (repo):** keep §6 aligned with `categories_and_rules/host_academic_models.json` and `categories_and_rules/positioning_tags.json`. After changing those files, run `node peer-atlas-viewer/tools/write-dev-catalog.mjs` so the dev viewer’s `dev/viewer-categories.json` stays in sync.

---

## 7. Example patch (illustrative)

```json
{
  "patch_metadata": {
    "created_at": "2026-05-08",
    "created_by": "external-agent",
    "source_corpus_name": "MDes Peer Program Comparator Corpus",
    "notes": "Per operator: set host model to design_hosted; add ui_ux to tags."
  },
  "changes": [
    {
      "program_id": "example_univ_mdes",
      "path": "identity.host_academic_model",
      "old_value": "unknown",
      "new_value": "design_hosted",
      "notes": "Operator instruction verbatim."
    },
    {
      "program_id": "example_univ_mdes",
      "path": "positioning.positioning_tags",
      "old_value": ["professional"],
      "new_value": ["professional", "ui_ux"],
      "notes": "Operator asked to add ui_ux."
    }
  ]
}
```

Replace values with those that match the real snapshot and operator request.

---

## 8. How your operator applies this (reference only)

```text
peer-atlas merge-patch path/to/your_patch.json
```

If `old_value` no longer matches because the corpus changed, the operator re-runs `export_snapshot.py` (no arguments), refreshes the full snapshot, and asks you again.

---

## 9. Operating rules for this task

- **No web search** and no use of URLs not given by the operator in the prompt.
- Implement **only** what the operator requested, using the **snapshot** as the source of truth for `old_value`.
- **`curriculum` in the snapshot** (`curriculum_summary`, `electives.summary`) is **read-only** context; do not emit `curriculum.*` patch paths.
- **`llm_rationales` in the snapshot** are read-only ingest notes; do not patch them.
- If instructions conflict with the snapshot (e.g. wrong `old_value`), state the conflict in `patch_metadata.notes` and produce an empty `changes` array **or** only the changes you can apply safely—whichever your operator prefers; when in doubt, **empty `changes`** and explain.

---

## 10. Checklist before you return output

- [ ] Root object has **only** `patch_metadata` and `changes`.
- [ ] Every `path` starts with `identity.` or `positioning.` only.
- [ ] No patches to `llm_rationales`, **`curriculum.*`**, `degree_cost`, or other out-of-scope paths.
- [ ] Every `host_academic_model` and every tag is **exactly** an id from §6.
- [ ] `positioning.positioning_tags` has **no duplicates**.
- [ ] Each `old_value` matches the supplied snapshot for that **`program_id`** and **`path`** at apply time (find the right row in `programs` before copying values).
- [ ] You did **not** use web search; all `new_value` content comes from operator instructions + snapshot.
