You output only valid JSON. No markdown fences, no commentary.

Return a single JSON object with these keys only (use null for unknown; arrays may be empty):

- **`official_program_label`**: One concise phrase suitable for **web search** alongside other keywords — include institution and degree/program name as printed on the page (e.g. "UC Berkeley Master of Information Management and Systems"). Prefer the **canonical program name** over marketing slogans.
- **`short_institution`**: Short host name for search (e.g. "UC Berkeley School of Information") or null.
- **`degree_subject_keywords`**: Up to **8** short tokens or phrases from the page that help disambiguate this program in search (e.g. "MIMS", "information management", "data science"). Omit generic words like "university" unless needed.

Use only the **SEED_PAGE_MARKDOWN** and **PROGRAM_CONTEXT_JSON**; do not invent facts not supported by the page text.

SEED_URL:
{{SEED_URL}}

PROGRAM_CONTEXT_JSON (may be partial; seed page is authoritative for names):
{{PROGRAM_CONTEXT_JSON}}

SEED_PAGE_MARKDOWN:
{{SEED_PAGE_MARKDOWN}}
