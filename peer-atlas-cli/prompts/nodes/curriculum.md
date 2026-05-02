You output only valid JSON. No markdown fences, no commentary.

Return a single JSON object with exactly one top-level key: `"curriculum"`.
The value must match the **curriculum** subtree (derived_features; core_courses[]; elective_requirements[]; sources[]; derivation_notes[]).

Rules:
- unit_system and sequencedness must be allowed ids from CATEGORY_JSON (unit_systems, sequencedness). For **sequencedness**, use the vocabulary’s **rules** and **corpus calibration** examples: the main distinction between **highly_sequenced** and **partially_sequenced** is the **share of required curriculum items** (especially core/plan rows) that have an **explicit designated semester or term** in official materials—not just “Year 1”. When **about two-thirds or more** of those items are term-specific, prefer **highly_sequenced**; when a substantial minority lack term-level placement, prefer **partially_sequenced** (see **Berkeley MDes** vs **Berkeley MIMS** in CATEGORY_JSON sequencedness rules).
- core_courses[].primary_type and secondary_type must be allowed course_types ids; secondary_type must be null if primary_type is design_studio.
- Each core course needs course_id, course_title, units_or_credits (number or null), normalized_unit_weight (null ok — tooling may recompute), sequence_position (int or null), course_summary, **source_url** (program base_url or a cited evidence URL).

**elective_requirements[] (critical):** each element must be one **electiveRequirement** object — the same field model as a single elective “slot”, not a policy summary blob.

For **every** item in `elective_requirements`, include exactly these keys (use null only where allowed):

- **requirement_name** (string): short label, e.g. `Technical elective`, `Open elective slot 1`.
- **requirement_description** (string): one or two sentences describing the rule.
- **units_or_credits** (number or null): typical units for that slot if known, else null.
- **normalized_unit_weight** (number or null): null is ok (tooling may recompute).
- **primary_type** (string): a **course_types** id from CATEGORY_JSON (same vocabulary as core_courses.primary_type). Pick the best-matching type for that bucket (e.g. technology, entrepreneurship, open_or_other).
- **secondary_type** (string or null): another course_types id or null; must be null if primary_type is design_studio.
- **course_summary** (string): brief text describing what counts toward this requirement.
- **source_url** (non-empty string): evidence URL.

**Do not** use keys such as `requirement_type`, `count`, `allowed_types`, or `description` (use **requirement_name** / **requirement_description** instead). **Do not** add any other properties — `additionalProperties` is false.

If the program describes four electives with different rules, emit **one object per rule or per slot** (e.g. four rows) each conforming to the list above.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `curriculum` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: curriculum

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
