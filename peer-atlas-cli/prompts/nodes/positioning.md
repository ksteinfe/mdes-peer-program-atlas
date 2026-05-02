You output only valid JSON. No markdown fences, no commentary.

Return a single JSON object with exactly one top-level key: `"positioning"`.
The value must match the **positioning** subtree of the MDes Peer Program corpus (derived_features with positioning_summary, positioning_tags; sources[]; derivation_notes[]).

Rules:
- **positioning_tags** is a flat array of zero or more distinct ids from CATEGORY_JSON **`positioning_tags`** (see `categories_and_rules/positioning_tags.json`). Order most salient first if multiple apply.
- **Evidence gate:** include a tag **only** when the **EVIDENCE** text (or a cited `sources[]` page summarized in evidence) **directly and explicitly** supports that tag’s meaning—e.g. same theme in program-authored copy, not guesswork from prestige, location, or “might be true” defaults. If support is weak, indirect, or purely associative, **omit** the tag. Prefer a **shorter, well-supported** tag list over a padded list.
- Each source object: **url** (unique id for the source), **llm_title** (short label, e.g. `Program 'About' page` or `Tuition & fees`), **llm_summary** (what this page contributes as evidence), **retrieved_date** (ISO date string, may be "").
- Each derivation_notes item: derived_feature, **source_url** (same string as a source.url you cite), note.
- Prefer evidence; if unknown, use null for optional strings where the ingest draft allows it, or "" only where the schema requires a string.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `positioning` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: positioning

PROGRAM_JSON (all nodes so far; you only update positioning):
{{PROGRAM_JSON}}

EVIDENCE (search + fetched pages):
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
