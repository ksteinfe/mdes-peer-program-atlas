"""OpenAI-compatible chat completions client."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Protocol

import httpx

from peer_atlas_cli.llm_transcript import record_llm_exchange


class LLMClient(Protocol):
    def complete(
        self, *, system: str, user: str, transcript_step: str | None = None
    ) -> str: ...


def _retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    raw = response.headers.get("Retry-After")
    if raw:
        try:
            return min(max(float(raw), 0.5), 120.0)
        except ValueError:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return min(
                    max((dt - datetime.now(timezone.utc)).total_seconds(), 0.5),
                    120.0,
                )
            except Exception:
                pass
    return min(2.0 * (2**attempt), 60.0)


def _api_error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
        err = data.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if isinstance(err, str):
            return err
    except Exception:
        pass
    return (response.text or "")[:800]


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 6,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base = (base_url or "https://api.openai.com").rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries

    def complete(
        self, *, system: str, user: str, transcript_step: str | None = None
    ) -> str:
        req_chars = len(system) + len(user)
        step_s = ""
        if transcript_step:
            ts = transcript_step if len(transcript_step) <= 42 else transcript_step[:39] + "…"
            step_s = f" · {ts}"
        print(f"[pa] LLM {req_chars}c{step_s}", file=sys.stderr)
        url = f"{self._base}/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        last_body = ""
        with httpx.Client(timeout=self._timeout) as client:
            for attempt in range(self._max_retries):
                r = client.post(url, headers=headers, json=payload)
                if r.status_code in (429, 503):
                    last_body = _api_error_message(r)
                    wait = _retry_after_seconds(r, attempt)
                    if attempt + 1 >= self._max_retries:
                        raise RuntimeError(
                            f"LLM API returned {r.status_code} after {self._max_retries} attempts. "
                            f"Wait and retry, or check usage/billing limits. Last detail: {last_body}"
                        )
                    print(
                        f"[pa] HTTP {r.status_code} · retry {wait:.1f}s ({attempt + 1}/{self._max_retries})",
                        file=sys.stderr,
                    )
                    time.sleep(wait)
                    continue
                try:
                    r.raise_for_status()
                except httpx.HTTPStatusError as e:
                    msg = _api_error_message(r)
                    raise RuntimeError(
                        f"LLM API error {r.status_code}: {msg or r.reason_phrase}"
                    ) from e
                data = r.json()
                try:
                    content = str(data["choices"][0]["message"]["content"])
                except (KeyError, IndexError, TypeError) as e:
                    raise RuntimeError(f"Unexpected LLM response: {data!r}") from e
                record_llm_exchange(
                    system=system,
                    user=user,
                    response=content,
                    step_slug=transcript_step,
                )
                return content


PROVIDERS: dict[str, type[OpenAICompatibleClient]] = {
    "openai": OpenAICompatibleClient,
}


def get_client(provider: str, *, api_key: str, model: str, base_url: str | None) -> LLMClient:
    key = provider.lower().strip()
    cls = PROVIDERS.get(key)
    if cls is None:
        raise SystemExit(f"Unsupported LLM_PROVIDER: {provider!r}. Supported: {', '.join(PROVIDERS)}")
    return cls(api_key=api_key, model=model, base_url=base_url)


def strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def parse_json_response(text: str) -> Any:
    raw = strip_json_fence(text)
    return json.loads(raw)
