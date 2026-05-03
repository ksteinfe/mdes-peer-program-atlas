You output only valid JSON. No markdown fences, no commentary.

Return a JSON object with top-level key **`"verification"`** and **`"llm_rationales"`** (array; include at least one row citing the page(s) that support **`status`** and any other fields you set).

The **`verification`** value must match the subtree exactly: **status**, **verified_by**, **verified_date** (three string keys only). Do **not** nest **`llm_rationales`** inside **`verification`**.

Rules:
- **`llm_rationales`:** each object has exactly **`feature`**, **`source_url`**, **`note`**, **`llm_title`**, **`retrieved_date`** (strings). Use **`feature`** paths like `verification.status`.
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
