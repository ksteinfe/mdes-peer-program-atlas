You write **plain prose only**. Use **as much length as you need**—there is **no word limit**; be thorough when the evidence is rich, concise when it is thin. Prefer flowing paragraphs over long bullet lists unless a short list clearly helps readability. No JSON, no markdown code fences.

Summarize **only what the fetched EVIDENCE supports** about how this program’s curriculum works. (This digest prompt is optional / experimental; ingest does not persist its output on the program record.)

**Include when the evidence allows:**
- **Core (and other named) courses** with **titles and catalog numbers/codes** as they appear in the evidence.
- **Term or semester placement** (e.g. Fall year 1, Spring, “first year”) when the evidence ties a course to a term; use cautious wording when sequencing is partial or unclear.
- The **nature of electives**: open vs structured areas, minimum counts or units, distribution rules, capstone vs free electives—whatever the pages actually say.
- A brief mention of **tracks or specializations** only if the evidence describes them.

If something is not stated in EVIDENCE, do not invent it.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `curriculum_digest` → `extra_instructions`):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: curriculum_digest

PROGRAM_CONTEXT_JSON:
{{PROGRAM_CONTEXT_JSON}}

EVIDENCE:
{{EVIDENCE}}
