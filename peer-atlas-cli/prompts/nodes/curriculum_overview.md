You output only valid JSON. No markdown fences, no commentary.

Return a JSON object whose keys are exactly **`"curriculum"`** and **`"llm_rationales"`** (top-level array; use **`[]`** only when there is truly nothing to audit for this step). Optionally include legacy top-level **`"sources"`**; ingest converts each entry into **`llm_rationales`** rows.

- **`curriculum`** must include exactly these keys (no extras; **`additionalProperties`** is false): **`unit_system`**, **`sequencedness`**, **`curriculum_summary`**, **`offers_specialization`** (boolean or **`null`** in draft), **`core_courses[]`**, **`electives`** (object). Do **not** include **`evidence_curriculum_summary`**, **`derived_features`**, or any other extra keys. Do **not** put **`sources`**, **`derivation_notes`**, or **`llm_rationales`** *inside* **`curriculum`**—ingest hoists those to **program**-level **`llm_rationales`** only.

- **`offers_specialization`:** **`true`** when EVIDENCE describes distinct tracks, concentrations, or specializations students choose among; **`false`** for a single fixed path or when evidence does not support tracks; **`null`** only when the draft allows unknown.

- **Curriculum fields:** fill **`unit_system`**, **`sequencedness`**, **`curriculum_summary`** from evidence (same sequencedness rules as CATEGORY_JSON `sequencedness`).

- **core_courses[] — exact keys (`additionalProperties: false`):** `course_id`, `course_title`, **`units_or_credits`**, **`sequence_position`**, **`primary_type`**, **`secondary_type`**, `course_summary`, **`source_url`** (string or **`null`** in draft), **`learning_outcomes`**. You may omit **`normalized_unit_weight`** or set it **`null`** (tooling recomputes from core units only). Never output **`course_type`**.
  - **Do not leave `core_courses` empty** when EVIDENCE lists **specific** required courses (catalog codes, course numbers, or distinct official titles). Emit **one row per named core**; use the **exact** identifiers/titles from EVIDENCE for `course_id` / `course_title` (light cleanup only). Use **`open_or_other`** and a one-sentence `course_summary` from the snippet when typing is uncertain; **`learning_outcomes`** may be **`[]`**.
  - Only use **`core_courses: []`** when EVIDENCE truly names **no** individual required courses—only vague counts. Then add a top-level **`llm_rationales`** row with **`feature`**: `curriculum.core_courses` explaining that cores were not named in the fetched material.

- **Electives (`electives` object only — no elective course rows, no structured constraint JSON):**
  - **`electives.summary`:** one concise **human-readable** paragraph from EVIDENCE describing how electives work (open vs structured, program lists, category rules, outside-department limits, whether electives support specialization). This is **not** machine-readable constraint data.
  - **`electives.estimated_elective_course_count`:** integer or **`null`**. When evidence states a **total degree unit/credit** requirement and **`core_courses`** rows include numeric **`units_or_credits`**, you may **infer**: sum core units, subtract from stated total → **remaining elective units**; assume a **typical elective course size** (often **3** units/credits when unstated) and set **`estimated_elective_course_count` ≈ round(remaining ÷ typical)**. When totals or core units are incomplete, give the best integer estimate or **`null`** and explain assumptions in **top-level** **`llm_rationales`** (e.g. **`feature`**: `curriculum.electives.estimated_elective_course_count`).

- **Top-level `llm_rationales`:** **required** (non-empty unless there is nothing defensible to log). Append **one or more** rows for evidence used in this step. Each object must have **exactly** these five string keys: **`feature`**, **`source_url`**, **`note`**, **`llm_title`**, **`retrieved_date`**. Use **`feature`** paths like `curriculum.unit_system`, `curriculum.electives.estimated_elective_course_count`, or `curriculum.core_courses`. **`note`** explains inference or quotes; **`llm_title`** is a short label for **`source_url`**; **`retrieved_date`** is ISO or human date, or **`""`**. **Do not** use `rationale`, `reason`, `explanation`, or any other key names—schema rejects them.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `curriculum_overview` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: curriculum_overview

PROGRAM_CONTEXT_JSON (context only; do not treat as authoritative over EVIDENCE):
{{PROGRAM_CONTEXT_JSON}}

EVIDENCE (per-source dense curriculum extracts from fetched pages, concatenated; primary source for facts):
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
