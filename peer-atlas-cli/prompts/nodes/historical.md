You output only valid JSON. No markdown fences, no commentary.

Return a JSON object with top-level key **`"historical"`** and **`"llm_rationales"`** (array).

- **`historical`**: a JSON **array** of objects. Each object has exactly two keys:
  - **`academic_year`** (string): the academic year label (e.g. `"2022-23"`).
  - **`degrees_granted`** (integer or null): number of completed degrees for that year. Use null when a year is mentioned but count is uncertain.
- An empty array `[]` is valid when EVIDENCE has no completion counts.

Rules:
- Only include years explicitly supported by EVIDENCE (IPEDS Completions survey, institutional fact books, annual reports, program stats pages).
- Counts are **completed degrees**, not enrollment.
- Do **not** invent or interpolate values not in EVIDENCE.
- **`llm_rationales[]`:** each object has exactly five string keys: **`feature`**, **`source_url`**, **`note`**, **`llm_title`**, **`retrieved_date`**. Use feature paths like `historical.0.degrees_granted` or `historical`. Include at least one row.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `historical` → `extra_instructions`):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: historical

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
