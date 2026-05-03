Category files were edited. Reclassify only the fields that depend on the impacted category set.

IMPACTED_FIELDS (dot paths; only edit these):
{{IMPACTED_PATHS}}

EXISTING_PROGRAM_JSON:
{{PROGRAM}}

OPTIONAL_REFRESHED_PAGE_TEXT (may be empty):
{{REFRESHED_SOURCES}}

CATEGORY_JSON:
{{CATEGORIES}}

Output JSON ONLY:
{
  "updates": [ { "path": "...", "value": ... } ],
  "llm_rationales_to_append": [ { "feature": "", "source_url": "", "note": "" } ]
}

Rules:
- Only change values for paths listed in IMPACTED_FIELDS (or their legitimate sub-keys if you must set a whole object—prefer leaf paths).
- Use only allowed ids from CATEGORY_JSON.
- For **positioning_tags**, keep or assign a tag **only** when refreshed page text or the cited program evidence **directly** supports that tag; do not add tags without explicit support in the provided material.
- If a value is already valid under new categories, you may return an empty updates array.
