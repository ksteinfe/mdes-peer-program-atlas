You write **plain prose only**—dense, factual, no JSON and no markdown code fences. Use **as much length as needed** for this single page; there is **no word limit**.

You will see **one** fetched web page (full excerpt) for **SOURCE_URL** below, plus minimal program context. Extract **everything on this page that could inform how this program’s curriculum works**—not only formal degree requirements: degree structure, length and pace, units/credits, required vs elective work, **named courses with catalog codes or numbers**, sequencing or terms when stated, capstone/thesis/internship or field experience, projects and studios, tracks or concentrations, policies about electives from other departments, learning outcomes or competency lists, advising or milestone language, and any other text that plausibly describes **what students study or must complete**.

**Rules**
- Ground every claim in the page text; if the page does not mention something, **do not** infer it from general knowledge.
- Prefer **compact paragraphs**; short bullet lists are fine for enumerated requirements or course lists.
- **Err on the side of inclusion**: if the page mixes marketing with a few concrete curriculum facts, **report those facts**. Weak or tangential signals are still worth a short note when they are clearly tied to coursework, structure, or degree experience.

Additional instructions (`categories_and_rules/node_prompt_rules.json` → key `curriculum_source_extract` → `extra_instructions`):
{{NODE_PROMPT_RULES}}

ACTIVE_NODE: curriculum_source_extract

PROGRAM_CONTEXT_JSON:
{{PROGRAM_CONTEXT_JSON}}

SOURCE_URL:
{{SOURCE_URL}}

PAGE_TEXT (simplified markup: head excerpt with title/description/canonical, then ``main`` / article / body-field region when detected; ``a href``, ``id``, ``img`` src/alt kept):
{{PAGE_TEXT}}
