You output only valid JSON. No markdown fences, no commentary.

Return a JSON object with top-level key **`"degree_cost"`** and **`"llm_rationales"`** (array; append at least one row per distinct fee/tuition source you relied on).

- **`degree_cost`** must contain only these keys (flat on the object):
  - **`base_currency`** (string, e.g. `USD`; use `""` if unknown)
  - **`exchange_rate_to_usd`** (number or null)
  - **`comparison_cost_usd`** (number or null) — **tuition + mandatory program/academic fees only** for cross-program comparison (not full COA / living expenses)
  - **`total_degree_cost_base_currency`** (number or null) — one program-stated total in **`base_currency`** when the evidence supports it (same tuition-and-fees scope when possible)

Rules:
- **Tuition & fees vs. COA:** If a page only gives a bundled cost-of-attendance total with no isolated tuition-and-fees subtotal, leave **`comparison_cost_usd`** null and explain in **`llm_rationales`**.
- **Top-level `llm_rationales`:** each object has exactly **`feature`**, **`source_url`**, **`note`**, **`llm_title`**, **`retrieved_date`** (strings). **`feature`** names the field it supports (e.g. `degree_cost.comparison_cost_usd`, `degree_cost.total_degree_cost_base_currency`).

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `degree_cost` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: degree_cost

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
