You output only valid JSON. No markdown fences, no commentary.

Return a JSON object with top-level key **`"positioning"`** and optionally **`"llm_rationales"`** (array).

- **`positioning`** must contain only **`positioning_summary`** (string) and **`positioning_tags`** (array of ids). No nested `derived_features`, `sources`, or `llm_rationales` inside **`positioning`**.
- **positioning_tags** is a flat array of zero or more distinct ids from CATEGORY_JSON **`positioning_tags`**. Order most salient first if multiple apply.

- Put supporting citations and rationale in optional top-level **`llm_rationales`**: each item **`feature`**, **`source_url`**, **`note`** (three strings only). Use **`feature`** paths like `positioning.positioning_tags` or `positioning.positioning_summary`. You may use **`[]`** if nothing needs noting.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `positioning` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: positioning

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
