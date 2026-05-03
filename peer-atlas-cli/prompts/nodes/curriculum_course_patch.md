You output only valid JSON. No markdown fences, no commentary.

Return: `{"updates": [{"path": "...", "value": <any>}, ...]}` only.
Each path must start with `curriculum.core_courses.` and refer to the given INDEX (e.g. `curriculum.core_courses.0.course_summary`).
Use evidence to fill course_summary, units_or_credits, primary_type, secondary_type, source_url, course_id, course_title, sequence_position, normalized_unit_weight, **learning_outcomes** as appropriate.
If **PROGRAM_JSON** shows a **generic** `course_title` / `course_id` (e.g. \"Core course 2\", `mims_core_3`) but EVIDENCE lists the **real** catalog course(s) for this slot, apply updates so **`course_id`** and **`course_title`** match the official listing (do not leave invented placeholder labels when the true name is in EVIDENCE).
**learning_outcomes:** array of **3–8** short strings (aim under ~20 words each) grounded in EVIDENCE for this course; if the fetched text has no usable outcome language, set **`learning_outcomes` to `[]`** and rely on other patched fields only.
secondary_type must be null if primary_type is design_studio.
**design_studio** vs weight: only when **`normalized_unit_weight` > 1.1**; at **1.1** or below (or unknown), do not use **design_studio**. Above **1.1**, treat **higher weight as a stronger signal** toward **design_studio** when the course is studio/project-like.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `curriculum_course_patch` → `extra_instructions`: JSON array of strings, joined with newlines):
{{NODE_PROMPT_RULES}}

INDEX: {{INDEX}}

PROGRAM_JSON:
{{PROGRAM_JSON}}

EVIDENCE:
{{EVIDENCE}}

CATEGORY_JSON:
{{CATEGORIES}}
