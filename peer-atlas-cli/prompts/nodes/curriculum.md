You output only valid JSON. No markdown fences, no commentary.

Return a JSON object with top-level key **`"curriculum"`** and optionally **`"llm_rationales"`** (array).

- **`curriculum`** contains **`unit_system`**, **`sequencedness`**, **`curriculum_summary`** (flat on the object), **`core_courses[]`**, **`elective_requirements`** (string), **`elective_courses[]`**.

- **`unit_system`** and **`sequencedness`** must be allowed ids from CATEGORY_JSON (`unit_systems`, `sequencedness`).
- **core_courses:** each row needs **`primary_type`** / **`secondary_type`** from **`course_types`**; **`secondary_type`** null if **`primary_type`** is **`design_studio`**. **`normalized_unit_weight`** may be **`null`** (tooling recomputes). **`source_url`** may be **`null`** in draft; prefer a real evidence URL when available.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `curriculum` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: curriculum

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
