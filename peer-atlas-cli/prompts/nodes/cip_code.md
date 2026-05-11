You output only valid JSON. No markdown fences, no commentary.

Return a JSON object with exactly two top-level keys: **`"cip_code"`** and **`"rationale"`**.

- **`cip_code`**: the best-matching id from CATEGORY_JSON (cip_codes), or `"unknown"` if the program is US-based but no code fits, or `null` if `identity.ipeds_unitid` is null or absent (meaning the institution is not IPEDS-enrolled and CIP codes do not apply).
- **`rationale`**: an object with exactly five string keys: `feature`, `source_url`, `note`, `llm_title`, `retrieved_date`.
  - `feature`: `"identity.cip_code"`
  - `source_url`: `""` (classification is based on program description only — no web source)
  - `note`: explain which program characteristics (degree type, positioning, curriculum focus) drove the selection, and note any close alternatives considered. If null, explain that the institution has no IPEDS UnitID on record.
  - `llm_title`: `"CIP code classification"` (or `"CIP code not applicable"` if null)
  - `retrieved_date`: `""`

Rules:
- Check `identity.ipeds_unitid` in PROGRAM_CONTEXT. If null or absent → `cip_code: null`.
- If ipeds_unitid is set → pick the single best-matching id from CATEGORY_JSON (cip_codes).
- Use `"unknown"` only when ipeds_unitid is set but no code in the list fits.
- Never invent a code not present in the list.
- Base the classification solely on the program description provided — do not use outside knowledge about rankings or reputation.

PROGRAM_CONTEXT:
{{PROGRAM_CONTEXT}}

CATEGORY_JSON:
{{CATEGORIES}}
