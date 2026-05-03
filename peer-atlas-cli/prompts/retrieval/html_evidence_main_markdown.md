You convert **simplified page HTML** (already stripped of scripts, images, most attributes, and with whitespace normalized) into **Markdown** that captures **only the main editorial / page content**.

**Include**
- Headings, paragraphs, lists, and tables that belong to the **primary article or page body** (degree requirements, course lists, policy prose, etc.).
- All factual detail needed to understand that main content (numbers, course codes, units, dates, links as plain text when the source had link text, etc.).

**Exclude**
- Site chrome: global navigation, mega-menus, breadcrumbs, “skip to content”, utility bars.
- Repeated boilerplate (footer columns, social blocks, newsletter signup, copyright lines) unless it is **unique** substantive policy for this page.
- Duplicate blocks that repeat the same marketing blurb shown site-wide.

If the page is mostly chrome with little unique body text, output **only** what is clearly main content (even if short). Do **not** invent content.

**Output rules**
- Return **Markdown only** (no JSON, no YAML). Do **not** wrap the answer in markdown code fences (no \`\`\` fences).
- Prefer `##` / `###` headings that mirror the page structure; use `-` lists where appropriate.
- Do not add a preamble like “Here is the markdown:”.

**SOURCE_URL** (for context only; do not echo it unless it helps structure):
{{SOURCE_URL}}

**CLEANED_HTML**:
{{CLEANED_HTML}}
