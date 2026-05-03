You output only valid JSON. No markdown fences, no commentary.

Return a JSON object whose keys are exactly **`"curriculum"`** and optionally **`"llm_rationales"`** (array).

- **`curriculum`** must match the subtree: **`unit_system`**, **`sequencedness`**, **`curriculum_summary`**, **`offers_specialization`** (boolean), **`core_courses[]`**, **`elective_requirements`** (string), **`elective_courses[]`**. Do **not** include any **`evidence_curriculum_summary`** field (it is not part of the corpus). There are **no** `sources` or `llm_rationales` arrays inside **`curriculum`**.

- **`offers_specialization`:** **`true`** when EVIDENCE describes distinct tracks, concentrations, or specializations students choose among; **`false`** for a single fixed path or when evidence does not support tracks.

- **Curriculum fields:** fill **`unit_system`**, **`sequencedness`**, **`curriculum_summary`** from evidence (same sequencedness rules as CATEGORY_JSON `sequencedness`).

- **core_courses[] — exact keys (`additionalProperties: false`):** `course_id`, `course_title`, **`units_or_credits`**, **`sequence_position`**, **`primary_type`**, **`secondary_type`**, `course_summary`, **`source_url`** (string or **`null`** in draft), **`learning_outcomes`**. You may omit **`normalized_unit_weight`** or set it **`null`** (tooling recomputes). Never output **`course_type`**.
  - **Do not leave `core_courses` empty** when EVIDENCE lists **specific** required courses (catalog codes, course numbers, or distinct official titles). Emit **one row per named core**; use the **exact** identifiers/titles from EVIDENCE for `course_id` / `course_title` (light cleanup only). Use **`open_or_other`** and a one-sentence `course_summary` from the snippet when typing is uncertain; **`learning_outcomes`** may be **`[]`**.
  - Only use **`core_courses: []`** when EVIDENCE truly names **no** individual required courses—only vague counts. Then add a top-level **`llm_rationales`** row with **`feature`**: `curriculum.core_courses` explaining that cores were not named in the fetched material.

- **Electives:** **`elective_requirements`** is one human-readable string from EVIDENCE. **`elective_courses[]`** uses **lite rows** (`course_id` required). When EVIDENCE states **how many** electives or elective **units** students must take, **match that structure**: e.g. "10 electives" → **10** rows (`course_id` may be `Elective 1` … `Elective 10` with null units) **or** one row per **named** bucket repeated to satisfy the stated count—do **not** default to only three generic buckets unless EVIDENCE describes exactly three buckets.

- **Top-level `llm_rationales`:** optional. Each object must have **exactly** these three keys: **`feature`**, **`source_url`**, **`note`** (all strings; use **`""`** when unknown). **Do not** use `rationale`, `reason`, `explanation`, or any other key names—schema rejects them. Same three-key objects as elsewhere. Use **`feature`** paths like `curriculum.unit_system` or `curriculum.core_courses` when you omit data or rely on thin evidence.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `curriculum_overview` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: curriculum_overview

PROGRAM_CONTEXT_JSON (context only; do not treat as authoritative over EVIDENCE):
{{PROGRAM_CONTEXT_JSON}}

EVIDENCE (per-source dense curriculum extracts from fetched pages, concatenated; primary source for facts):
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
