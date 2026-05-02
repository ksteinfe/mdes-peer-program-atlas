"""Dot-path access for JSON-like dict/list structures."""

from __future__ import annotations

import copy
import re
from typing import Any


def parse_json_path(path: str) -> list[str | int]:
    if not path or not str(path).strip():
        raise ValueError("path must be non-empty")
    parts: list[str | int] = []
    rest = path.strip()
    while rest:
        if rest.startswith("."):
            rest = rest[1:]
            continue
        m = re.match(r"([^\.\[]+)", rest)
        if not m:
            raise ValueError(f"invalid path segment in {path!r} near {rest!r}")
        token = m.group(1)
        if re.fullmatch(r"[0-9]+", token):
            parts.append(int(token))
        else:
            parts.append(token)
        rest = rest[m.end() :]
        if rest.startswith("["):
            end = rest.find("]")
            if end == -1:
                raise ValueError(f"unclosed '[' in path {path!r}")
            parts.append(int(rest[1:end]))
            rest = rest[end + 1 :]
    return parts


def path_exists(obj: Any, path: str) -> bool:
    try:
        get_path(obj, path)
        return True
    except (KeyError, IndexError, TypeError):
        return False


def get_path(obj: Any, path: str) -> Any:
    cur = obj
    for p in parse_json_path(path):
        if isinstance(p, int):
            cur = cur[p]
        else:
            cur = cur[p]
    return cur


def set_path(obj: Any, path: str, value: Any) -> None:
    parts = parse_json_path(path)
    cur = obj
    for p in parts[:-1]:
        cur = cur[p]
    last = parts[-1]
    val = copy.deepcopy(value)
    if isinstance(last, int):
        cur[last] = val
    else:
        cur[last] = val


def ensure_path(
    obj: Any, path: str, *, allow_new: bool
) -> tuple[Any, str | int]:
    """Navigate to parent of final segment, creating dict keys as needed if allow_new."""
    parts = parse_json_path(path)
    if not parts:
        raise ValueError("empty path after parse")
    cur = obj
    for p in parts[:-1]:
        if isinstance(p, int):
            while len(cur) <= p:
                if not allow_new:
                    raise KeyError(f"missing list index {p} along path {path!r}")
                cur.append({})
            cur = cur[p]
        else:
            if p not in cur:
                if not allow_new:
                    raise KeyError(f"missing key {p!r} along path {path!r}")
                cur[p] = {}
            cur = cur[p]
    return cur, parts[-1]


def set_path_flexible(obj: Any, path: str, value: Any, *, allow_new_paths: bool) -> None:
    val = copy.deepcopy(value)
    if not allow_new_paths:
        set_path(obj, path, val)
        return
    parent, last = ensure_path(obj, path, allow_new=True)
    if isinstance(last, int):
        while isinstance(parent, list) and len(parent) <= last:
            parent.append(None)
        parent[last] = val
    else:
        parent[last] = val
