You output only valid JSON. No markdown fences, no commentary.

Return a JSON object with top-level key **`"identity"`** and **`"llm_rationales"`** (array; append at least one row citing the evidence used for identity fields).

- **`identity`** subtree: institution_name, program_name, credential_name, degree_type, host_academic_units[], host_academic_model, **`location_label`**, **`first_degree_granted_year`**, **`cip_code`**.

Rules:
- **host_academic_model** must be an allowed id from CATEGORY_JSON (host_academic_models).
- **`location_label`**: one human-readable string (city, region, country as appropriate); use **`""`** if unknown.
- **`first_degree_granted_year`**: four-digit string year the program first conferred a degree (e.g. `"1998"`). Check program history, "About" pages, accreditation records, or IPEDS data. Use `"unknown"` (never null) when not found in EVIDENCE.
- **`cip_code`**: CIP codes apply only to US institutions (IPEDS-enrolled). Check `identity.ipeds_unitid` in PROGRAM_JSON.
  - If `ipeds_unitid` is set and non-null → select the best-matching id from CATEGORY_JSON (cip_codes) (e.g. `"50.0401"`), or use `"unknown"` if no code fits. Never invent a code not in the list.
  - If `ipeds_unitid` is null or absent → set `cip_code` to `null` and add an **`llm_rationales`** row with `feature: "identity.cip_code"`, `source_url: ""`, `llm_title: "CIP code not applicable"`, `retrieved_date: ""`, and a `note` stating that CIP codes are a US federal (IPEDS) classification and this institution has no IPEDS UnitID on record.
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
