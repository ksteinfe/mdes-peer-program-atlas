"""Slug helpers for program_id."""

from __future__ import annotations

import re


def slugify(text: str, *, max_len: int = 48) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if len(s) > max_len:
        s = s[:max_len].rstrip("_")
    return s or "unknown"


def make_program_id(institution: str, program_name: str) -> str:
    return f"{slugify(institution)}_{slugify(program_name)}"
