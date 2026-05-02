You output only valid JSON. No markdown fences, no commentary.

Return a single JSON object with exactly one top-level key: `"duration"`.
The value must match the **duration** subtree (derived_features with length_in_berkeley_semesters integer or null, duration_category id; sources[]; derivation_notes[]).

Rules:
- duration_category must be an allowed id from CATEGORY_JSON (duration_categories).
- Sources and derivation_notes follow the same shape as in the corpus program schema.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `duration` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: duration

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
