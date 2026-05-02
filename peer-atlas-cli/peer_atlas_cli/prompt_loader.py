"""Load prompt templates from ``peer-atlas-cli/prompts/`` (under repo root), with package fallback."""

from __future__ import annotations

import pathlib

from peer_atlas_cli.repo_root import find_repo_root


def _package_prompts_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent / "prompts"


def _prompts_dir() -> pathlib.Path:
    try:
        root = find_repo_root()
    except FileNotFoundError:
        return _package_prompts_dir()
    candidate = root / "peer-atlas-cli" / "prompts"
    if candidate.is_dir():
        return candidate
    legacy = root / "prompts"
    if legacy.is_dir():
        return legacy
    return _package_prompts_dir()


def load_prompt(name: str) -> str:
    path = _prompts_dir() / name
    return path.read_text(encoding="utf-8")


def render_template(template: str, **kwargs: str) -> str:
    out = template
    for key, val in kwargs.items():
        out = out.replace("{{" + key + "}}", val)
    return out
