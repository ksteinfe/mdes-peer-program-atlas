You output only valid JSON. No markdown fences, no commentary.

Return a single JSON object with exactly one top-level key: `"verification"`.
The value must match the **verification** subtree exactly: **status**, **verified_by**, **verified_date** (three string keys only).

Rules:
- status must be an allowed id from CATEGORY_JSON (verification_statuses). For newly ingested programs use `llm_extracted` unless evidence warrants `needs_sources`.
- verified_by and verified_date: use `""` until a human verifies the record; after verification, use the verifier id or name and an ISO date string as appropriate.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `verification` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: verification

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
