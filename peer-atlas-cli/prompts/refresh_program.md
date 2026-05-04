You are refreshing an existing program record using new fetches and the prior JSON.

Input:
- EXISTING_PROGRAM_JSON: current record
- FETCHED_TEXT: newly fetched page text (may be empty)
- CATEGORY_JSON: allowed category ids

Output JSON with this shape ONLY:
{
  "merged_program": { ... full updated program object ... },
  "changed_paths": ["dot.path", ...],
  "new_llm_rationales": [
    {
      "feature": "dot.path.or.program.citation",
      "source_url": "https://...",
      "note": "what changed or was confirmed",
      "llm_title": "short page label",
      "retrieved_date": "ISO-or-empty"
    }
  ]
}

Rules:
- Preserve human-reviewed meaning: do not blank out fields unless the evidence clearly contradicts them; document residual uncertainty in **merged_program.llm_rationales** or **new_llm_rationales** as needed.
- Append **new_llm_rationales** onto **merged_program.llm_rationales** (dedupe by `source_url` + `feature` when the CLI merges). Each row uses the **five** string keys above.
- Keep program_id and **base_url** unchanged.
- Use only allowed category ids from CATEGORY_JSON.

EXISTING_PROGRAM_JSON:
{{PROGRAM}}

FETCHED_TEXT:
{{FETCHED}}

CATEGORY_JSON:
{{CATEGORIES}}
