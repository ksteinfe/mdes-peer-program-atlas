"""LLM: simplified HTML → main-content Markdown for evidence (nav / chrome removed)."""

from __future__ import annotations

import os
import re
import unicodedata
from typing import TYPE_CHECKING

from peer_atlas_cli.llm_nodes import _transcript_slug_for_source_url
from peer_atlas_cli.prompt_loader import load_prompt, render_template

if TYPE_CHECKING:
    from peer_atlas_cli.llm_client import LLMClient

_LLM_INPUT_CHARS = 120_000


def llm_input_char_limit() -> int:
    raw = os.environ.get("PEER_ATLAS_HTML_MARKDOWN_LLM_INPUT_CHARS", "").strip()
    if not raw:
        return _LLM_INPUT_CHARS
    try:
        return max(8_000, min(int(raw), 500_000))
    except ValueError:
        return _LLM_INPUT_CHARS


def skip_html_markdown_llm() -> bool:
    return os.environ.get("PEER_ATLAS_SKIP_HTML_MARKDOWN_LLM", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def sanitize_llm_text_for_json_storage(s: str) -> str:
    """
    Make LLM output safe to store in a JSON string: NFC normalization, strip most
    C0 control characters (keep tab/newline/carriage return), replace lone surrogates.
    """
    if not isinstance(s, str):
        return ""
    t = unicodedata.normalize("NFC", s)
    out: list[str] = []
    for ch in t:
        o = ord(ch)
        if o < 32 and ch not in "\t\n\r":
            out.append(" ")
        elif 0xD800 <= o <= 0xDFFF:
            out.append("\ufffd")
        else:
            out.append(ch)
    return "".join(out)


def _strip_markdown_fences(s: str) -> str:
    t = (s or "").strip()
    if not t.startswith("```"):
        return t
    lines = t.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _cap_cleaned_html_for_llm(cleaned_html: str, limit: int) -> str:
    h = (cleaned_html or "").strip()
    if len(h) <= limit:
        return h
    return h[:limit] + "\n\n[… truncated for LLM input …]"


def html_to_main_content_markdown(
    *,
    client: "LLMClient",
    cleaned_html: str,
    source_url: str,
) -> str:
    """
    One chat completion: simplified HTML → main-body Markdown (no nav boilerplate).
    """
    lim = llm_input_char_limit()
    block = _cap_cleaned_html_for_llm(cleaned_html, lim)
    tmpl = load_prompt("retrieval/html_evidence_main_markdown.md")
    user = render_template(
        tmpl,
        SOURCE_URL=(source_url or "").strip(),
        CLEANED_HTML=block,
    )
    system = (
        "You follow the instructions in the user message exactly. "
        "Output Markdown only; no JSON; no markdown code fences around the whole answer."
    )
    slug = _transcript_slug_for_source_url(source_url or "page")
    raw = client.complete(
        system=system,
        user=user,
        transcript_step=f"html-evidence-main-md__{slug}",
    )
    out = sanitize_llm_text_for_json_storage(_strip_markdown_fences(raw or ""))
    return out.strip()
