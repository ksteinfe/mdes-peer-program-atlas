You output only valid JSON. No markdown fences, no commentary.

Return a JSON object with top-level key **`"curriculum"`** and **`"llm_rationales"`** (array; append at least one row documenting evidence for this pass, or **`[]`** only when there is nothing to audit).

- **`curriculum`** contains **`unit_system`**, **`sequencedness`**, **`curriculum_summary`**, **`offers_specialization`**, **`core_courses[]`**, **`electives`** (`summary` + `estimated_elective_course_count`). Citations and rationales live at **program** top level in **`llm_rationales[]` only** — not under **`curriculum`**.

- **`unit_system`** and **`sequencedness`** must be allowed ids from CATEGORY_JSON (`unit_systems`, `sequencedness`).
- **core_courses:** each row needs **`primary_type`** / **`secondary_type`** from **`course_types`**; **`secondary_type`** null if **`primary_type`** is **`design_studio`**. **`normalized_unit_weight`** may be **`null`** (tooling recomputes from core course units). **`source_url`** may be **`null`** in draft; prefer a real evidence URL when available.
- **`electives`:** prose in **`summary`**; optional integer **`estimated_elective_course_count`** for visualization (infer from total vs core units when evidence supports it; document uncertainty in top-level **`llm_rationales`**).


Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `curriculum` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: curriculum

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
