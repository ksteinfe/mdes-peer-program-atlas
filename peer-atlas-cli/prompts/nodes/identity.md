You output only valid JSON. No markdown fences, no commentary.

Return a single JSON object with exactly one top-level key: `"identity"`.
The value must match the **identity** subtree (institution_name, program_name, credential_name, degree_type, host_academic_units[], host_academic_model, location, sources[]).

Rules:
- host_academic_model must be an allowed id from CATEGORY_JSON (host_academic_models).
- Use other populated program nodes (positioning, duration, curriculum, degree_cost) for consistency.
- location.country and location.state_or_region: use strings; use "" if unknown rather than null when possible.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `identity` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: identity

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
