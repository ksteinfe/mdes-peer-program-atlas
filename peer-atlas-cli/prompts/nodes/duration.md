You output only valid JSON. No markdown fences, no commentary.

Return a JSON object with top-level key **`"duration"`** and optionally **`"llm_rationales"`** (array).

- **`duration`** must contain only **`length_in_berkeley_semesters`** (integer or null) and **`duration_category`** (id from CATEGORY_JSON `duration_categories`).

- Put citations and rationale in optional top-level **`llm_rationales`** (objects with **`feature`**, **`source_url`**, **`note`** only). Example **`feature`**: `duration.duration_category`.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `duration` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: duration

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
