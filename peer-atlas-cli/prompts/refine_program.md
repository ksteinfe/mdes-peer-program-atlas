You apply a targeted edit to one program record.

Input:
- EXISTING_PROGRAM_JSON
- USER_INSTRUCTION: what to change
- CATEGORY_JSON
- OPTIONAL_EVIDENCE: fetched page excerpts (may be empty)

Output JSON ONLY:
{
  "updates": [
    { "path": "dot.path.with.optional[0].indices", "value": <any JSON value> }
  ],
  "llm_rationales_to_append": [
    {
      "feature": "path.or.field.supported",
      "source_url": "",
      "note": "",
      "llm_title": "",
      "retrieved_date": ""
    }
  ]
}

Rules:
- Only include paths that need to change. Paths use dot notation and bracketed indices.
- Preserve all unrelated data (CLI will apply updates surgically).
- Respect category ids from CATEGORY_JSON for any classification fields you touch.
- **llm_rationales_to_append:** each object has **feature**, **source_url**, **note**, **llm_title**, **retrieved_date** (strings only). Entries are appended to the program-level **llm_rationales** array.

EXISTING_PROGRAM_JSON:
{{PROGRAM}}

USER_INSTRUCTION:
{{INSTRUCTION}}

OPTIONAL_EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
