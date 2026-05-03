You output only valid JSON. No markdown fences, no commentary.

Return a JSON object with top-level key **`"identity"`** and optionally **`"sources"`** (array) and/or **`"llm_rationales"`** (array).

- **`identity`** must match the subtree: institution_name, program_name, credential_name, degree_type, host_academic_units[], host_academic_model, **`location_label`** only (no **`sources`** inside **`identity`**).

Rules:
- **host_academic_model** must be an allowed id from CATEGORY_JSON (host_academic_models).
- **`location_label`**: one human-readable string (city, region, country as appropriate); use **`""`** if unknown.
- **`sources[]`** (top-level, alongside **`identity`**): bibliography for this program (url, llm_title, llm_summary, retrieved_date). The merged program stores sources at the **program root** only.
- Use other populated program nodes for consistency where helpful.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `identity` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: identity

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
