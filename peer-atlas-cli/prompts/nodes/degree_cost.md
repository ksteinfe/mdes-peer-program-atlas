You output only valid JSON. No markdown fences, no commentary.

Return a single JSON object with exactly one top-level key: `"degree_cost"`.
The value must match the **degree_cost** subtree (derived_features with currency/cost fields; sources[]; derivation_notes[]).

Rules:
- cost_basis must be an allowed id from CATEGORY_JSON (cost_basis).
- Use null for unknown numeric costs when you truly have no basis; use "" for exchange_rate_date only if you must (prefer ISO date or null if draft allows).
- **derivation_notes[] (schema-required):** every object must include **exactly** these three string keys — **`derived_feature`**, **`source_url`**, **`note`** — and **no other keys**. Omitting **`derived_feature`** fails validation. **`derived_feature`** must name the **`degree_cost.derived_features`** field that note supports (e.g. `total_degree_cost_base_currency_single`, `total_degree_cost_base_currency_domestic_or_resident`, `cost_basis`, `comparison_cost_method`, `comparison_cost_usd`, `exchange_rate_date`, `base_currency`).
- Valid examples (each note is one object in the array):
  - `{"derived_feature":"total_degree_cost_base_currency_single","source_url":"https://design.berkeley.edu/admissions/program-fees-funding","note":"high — program table gives an explicit estimated total for required units across the degree; used as the single-total figure."}`
  - `{"derived_feature":"cost_basis","source_url":"https://grad.berkeley.edu/admissions/application-process/cost/","note":"Set to tuition_only because evidence covers tuition/program fees but not a full official COA line item for the program."}`
  - `{"derived_feature":"comparison_cost_usd","source_url":"https://design.berkeley.edu/learn-more-tuition-financial-aid","note":"low — left null; page references fees but excerpt does not give a verifiable USD total comparable across programs."}`

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `degree_cost` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: degree_cost

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
