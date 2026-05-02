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
  "derivation_notes_to_append": [
    { "section": "curriculum", "derived_feature": "", "source_url": "", "note": "" }
  ],
  "fields_needing_review_additions": ["path", ...]
}

Rules:
- Only include paths that need to change. Paths use dot notation and bracketed indices.
- Preserve all unrelated data (CLI will apply updates surgically).
- Respect category ids from CATEGORY_JSON for any classification fields you touch.
- derivation_notes_to_append: include `section` one of positioning|duration|degree_cost|curriculum. Omit fields not in schema for that section (use derived_feature, source_url, note only).

EXISTING_PROGRAM_JSON:
{{PROGRAM}}

USER_INSTRUCTION:
{{INSTRUCTION}}

OPTIONAL_EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
