"""Environment and LLM configuration (optional until LLM commands run)."""

from __future__ import annotations

import os
import pathlib

from dotenv import load_dotenv


def load_env(repo_root: pathlib.Path) -> None:
    env_path = repo_root / ".env"
    if env_path.is_file():
        load_dotenv(env_path)
    load_dotenv()


def require_llm_config() -> tuple[str, str, str, str | None]:
    provider = os.environ.get("LLM_PROVIDER", "openai").strip()
    model = os.environ.get("LLM_MODEL", "").strip()
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    base_url = os.environ.get("LLM_BASE_URL", "").strip() or None
    if not api_key:
        raise SystemExit(
            "LLM_API_KEY is missing. Set it in the repository root .env (see .env.example)."
        )
    if not model:
        raise SystemExit("LLM_MODEL is missing. Set it in .env (see .env.example).")
    return provider, model, api_key, base_url
