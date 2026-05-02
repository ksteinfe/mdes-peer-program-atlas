You output only valid JSON. No markdown fences, no commentary.

Return a single JSON object with exactly one top-level key: `"curriculum"`.
The value must match the **curriculum** subtree (derived_features; core_courses[]; **elective_requirements** (string); **elective_courses[]**; sources[]; derivation_notes[]).

Rules:
- unit_system and sequencedness must be allowed ids from CATEGORY_JSON (unit_systems, sequencedness). For **sequencedness**, use the vocabulary’s **rules** and **corpus calibration** examples: the main distinction between **highly_sequenced** and **partially_sequenced** is the **share of required curriculum items** (especially core/plan rows) that have an **explicit designated semester or term** in official materials—not just “Year 1”. When **about two-thirds or more** of those items are term-specific, prefer **highly_sequenced**; when a substantial minority lack term-level placement, prefer **partially_sequenced** (see **Berkeley MDes** vs **Berkeley MIMS** in CATEGORY_JSON sequencedness rules).
- core_courses[].primary_type and secondary_type must be allowed course_types ids; secondary_type must be null if primary_type is design_studio.
- Each core course needs course_id, course_title, units_or_credits (number or null), normalized_unit_weight (null ok — tooling may recompute), sequence_position (int or null), course_summary, **source_url** (program base_url or a cited evidence URL), **learning_outcomes** (array of short outcome strings; use `[]` only when no defensible outcomes exist from evidence).

**Electives (string + lite rows, no per-row research):**
- **`elective_requirements`**: one **string** — a clear, human-readable summary of how the program defines electives (counts, buckets, restrictions, what counts), taken **only** from program-published text in EVIDENCE (handbook, degree requirements, elective policy). Use **`""`** only when the evidence says nothing usable about electives.
- **`elective_courses[]`**: a short array of **course-like placeholders** — not Tavily-researched catalog rows. Each object has **exactly** three keys: **`course_id`** (string label such as **`Open Elective`**, **`Technical Elective`**, **`Studio elective`**, or similar bucket names), **`units_or_credits`** (number or **`null`**), **`normalized_unit_weight`** (number or **`null`** — tooling may recompute). Use **one row per distinct bucket or rule** the evidence supports; **`[]`** if electives are not broken out. **Do not** put named elective catalog courses here unless they are true required electives with codes in evidence; **do not** put elective buckets into **`core_courses[]`**.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `curriculum` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: curriculum

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
