You output only valid JSON. No markdown fences, no commentary.

Return a single JSON object with exactly one top-level key: `"curriculum"`.
The value must match the **curriculum** subtree (derived_features; core_courses[]; **elective_requirements** (string); **elective_courses[]**; sources[]; derivation_notes[]).

This pass is **curriculum overview**: establish program-level curriculum facts and **`core_courses[]` rows for each required core the evidence actually names** (official course numbers and titles as printed on the degree plan, catalog, or program requirements page). A later step will fetch per-course pages and refine each row.

Rules:
- **derived_features:** fill `unit_system`, `sequencedness`, flags, `total_units_or_credits`, `curriculum_summary` from evidence where possible (same rules as full curriculum: sequencedness from CATEGORY_JSON `sequencedness` rules; share of term-specific required items).
- **core_courses[] — exact keys (JSON Schema `additionalProperties: false`):** every object must include **only** these keys — no others (never **`course_type`**; use **`primary_type`** and **`secondary_type`** only):
  - `course_id`, `course_title` (strings)
  - **`units_or_credits`**: number **or** **`null`** if unknown (the key **must** be present)
  - **`normalized_unit_weight`**: number **or** **`null`** (the key **must** be present; tooling may recompute later)
  - `sequence_position`: integer **or** **`null`**
  - **`primary_type`**, **`secondary_type`**: each a **course_types** id from CATEGORY_JSON, or **`null`** where allowed; **`secondary_type` must be `null` if `primary_type` is `design_studio`**
  - `course_summary`, `source_url` (strings or null per draft)
  - **`learning_outcomes`**: array of strings; use **`[]`** in this pass
- **core_courses[] — content:** One row per **named** required core course you can extract from EVIDENCE (catalog code + title). **Do not** invent generic labels such as **"Core course 2"** or opaque ids like `mims_core_2` unless that is the real catalog key. If only some cores are named, output that many rows—do **not** pad. Prefer **`open_or_other`** for types when uncertain; avoid **`design_studio`** unless evidence clearly supports it.
- **Electives — `elective_requirements` (string) + `elective_courses[]`:** Set **`elective_requirements`** to a readable paragraph summarizing elective rules from EVIDENCE only (no web research per elective). Set **`elective_courses[]`** to **one lite object per bucket** the evidence supports, using **placeholder `course_id` labels** when needed (e.g. **`Open Elective`**, **`Technical Elective`**) with **`units_or_credits`** and **`normalized_unit_weight`** present (use **`null`** when unknown). These rows are **not** full `coreCourse` objects — **only** `course_id`, `units_or_credits`, `normalized_unit_weight`. If the evidence does not distinguish buckets, use **`[]`** for **`elective_courses`** and still set **`elective_requirements`** from whatever policy text exists (or **`""`** if none). **Do not** put elective catalog listings into **`core_courses[]`**.
- **sources** and **derivation_notes:** same shapes as the corpus schema; cite evidence for curriculum-level fields.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `curriculum_overview` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: curriculum_overview

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
