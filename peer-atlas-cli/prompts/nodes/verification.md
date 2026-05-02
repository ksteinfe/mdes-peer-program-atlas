You output only valid JSON. No markdown fences, no commentary.

Return a single JSON object with exactly one top-level key: `"verification"`.
The value must match the **verification** subtree (status, verified_by, verified_date, verification_scope[], verification_notes, fields_needing_review[]).

Rules:
- status must be an allowed id from CATEGORY_JSON (verification_statuses). For newly ingested programs use `llm_extracted` unless evidence warrants `needs_sources`.
- verified_by: use "" if not human-verified; verified_date: use "" or ISO date string.
- List any uncertain paths in fields_needing_review (string JSON paths like `duration.derived_features.duration_category`).

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `verification` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: verification

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
