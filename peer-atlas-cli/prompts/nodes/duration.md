You output only valid JSON. No markdown fences, no commentary.

Return a JSON object with top-level key **`"duration"`** and **`"llm_rationales"`** (array; append at least one row citing the evidence used).

- **`duration`** must contain only **`length_in_berkeley_semesters`** (integer or null) and **`duration_category`** (id from CATEGORY_JSON `duration_categories`).

- Put citations in top-level **`llm_rationales`** (objects with **`feature`**, **`source_url`**, **`note`**, **`llm_title`**, **`retrieved_date`** only). Example **`feature`**: `duration.duration_category`.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `duration` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: duration

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
