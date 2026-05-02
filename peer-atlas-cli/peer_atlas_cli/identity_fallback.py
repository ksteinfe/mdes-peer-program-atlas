"""Fill missing identity fields when the LLM omits them (URL/query heuristics)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def _s(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def apply_identity_fallbacks(program: dict[str, Any], *, url: str, query: str) -> bool:
    """
    Ensure program['identity'] is a dict with non-empty institution_name and program_name.
    Returns True if any field was written or repaired.
    """
    changed = False
    if not isinstance(program.get("identity"), dict):
        program["identity"] = {}
        changed = True
    ident: dict[str, Any] = program["identity"]

    inst = _s(ident.get("institution_name"))
    pname = _s(ident.get("program_name"))

    if url and (not inst or not pname):
        p = urlparse(url)
        host = (p.netloc or "").strip().replace("www.", "") or "unknown_host"
        path = (p.path or "").strip().strip("/")
        if not inst:
            ident["institution_name"] = host
            changed = True
        if not pname:
            if path:
                tail = path.split("/")[-1].replace("-", " ").replace("_", " ")
                ident["program_name"] = (tail[:120].title() if tail else "Program (from URL)")
            else:
                ident["program_name"] = "Program (from URL)"
            changed = True

    if query:
        if not _s(ident.get("program_name")):
            ident["program_name"] = query[:200]
            changed = True
        if not _s(ident.get("institution_name")) and not url:
            ident["institution_name"] = "Unknown institution (from query)"
            changed = True

    if not _s(ident.get("institution_name")):
        ident["institution_name"] = "Unknown institution"
        changed = True
    if not _s(ident.get("program_name")):
        ident["program_name"] = "Unknown program"
        changed = True

    return changed
