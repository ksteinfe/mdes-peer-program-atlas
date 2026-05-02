You are refreshing an existing program record using new fetches and the prior JSON.

Input:
- EXISTING_PROGRAM_JSON: current record
- FETCHED_TEXT: newly fetched page text (may be empty)
- CATEGORY_JSON: allowed category ids

Output JSON with this shape ONLY:
{
  "merged_program": { ... full updated program object ... },
  "changed_paths": ["dot.path", ...],
  "new_sources": [ { each source: **url** (unique id), **llm_title**, **llm_summary**, **retrieved_date** } ],
  "fields_needing_review_additions": ["dot.path", ...]
}

Rules:
- Preserve human-reviewed meaning: do not blank out fields unless the evidence clearly contradicts them; prefer marking fields_needing_review_additions.
- Append new_sources rather than replacing all sources (merge into appropriate sections' sources arrays without removing existing entries).
- Keep program_id and **base_url** unchanged.
- Use only allowed category ids from CATEGORY_JSON.

EXISTING_PROGRAM_JSON:
{{PROGRAM}}

FETCHED_TEXT:
{{FETCHED}}

CATEGORY_JSON:
{{CATEGORIES}}
