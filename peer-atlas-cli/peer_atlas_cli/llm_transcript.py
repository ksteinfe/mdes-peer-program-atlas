"""Per-CLI-invocation LLM request/response log under ``.peer-atlas/llm-last-session/``."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT: Path | None = None
_SEQ = 0


def session_dir(repo_root: Path) -> Path:
    return repo_root / ".peer-atlas" / "llm-last-session"


def sanitize_transcript_slug(label: str, *, max_len: int = 72) -> str:
    """Lowercase slug safe for Windows filenames: ``[a-z0-9_-]+``."""
    s = (label or "exchange").strip().lower()
    s = re.sub(r"[^a-z0-9_-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return (s or "exchange")[:max_len]


def begin_cli_llm_session(repo_root: Path, *, argv: list[str] | None = None) -> None:
    """
    Clear and recreate the log directory for this CLI process.
    Call once at the start of each ``peer-atlas`` invocation (before any LLM calls).
    """
    global _REPO_ROOT, _SEQ
    _REPO_ROOT = repo_root
    _SEQ = 0
    d = session_dir(repo_root)
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "argv": list(argv) if argv is not None else [],
    }
    (d / "_session.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def record_llm_exchange(
    *,
    system: str,
    user: str,
    response: str,
    step_slug: str | None = None,
) -> None:
    """Append one chat completion (system + user in, assistant text out)."""
    global _SEQ
    root = _REPO_ROOT
    if root is None:
        return
    _SEQ += 1
    d = session_dir(root)
    if not d.is_dir():
        return
    seq = f"{_SEQ:05d}"
    slug = sanitize_transcript_slug(step_slug or "exchange")
    base = f"{seq}--{slug}"
    req = (
        "=== system ===\n"
        + (system or "")
        + "\n\n=== user ===\n"
        + (user or "")
        + "\n"
    )
    (d / f"{base}-request.txt").write_text(req, encoding="utf-8", errors="replace")
    (d / f"{base}-response.txt").write_text(
        response or "",
        encoding="utf-8",
        errors="replace",
    )
