You output only valid JSON. No markdown fences, no commentary.

Return a JSON object with top-level key **`"identity"`** and **`"llm_rationales"`** (array; append at least one row citing the evidence used for identity fields). Optionally include legacy **`"sources"`**; ingest converts each entry into **`llm_rationales`** rows.

- **`identity`** must match the subtree: institution_name, program_name, credential_name, degree_type, host_academic_units[], host_academic_model, **`location_label`** only (no **`sources`** inside **`identity`**).

Rules:
- **host_academic_model** must be an allowed id from CATEGORY_JSON (host_academic_models).
- **`location_label`**: one human-readable string (city, region, country as appropriate); use **`""`** if unknown.
- **`llm_rationales[]`:** each object has **exactly** five string keys: **`feature`**, **`source_url`**, **`note`**, **`llm_title`**, **`retrieved_date`**. Use **`feature`** paths under **`identity.*`**. **`note`** summarizes what the cited page supports; **`llm_title`** labels **`source_url`**; **`retrieved_date`** or **`""`**.
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
