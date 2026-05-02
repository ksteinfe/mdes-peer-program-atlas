"""program_draft.schema.json atlas_ingest.stage.enum must match ATLAS_INGEST_STAGES."""

from __future__ import annotations

import json

from peer_atlas_cli.program_skeleton import ATLAS_INGEST_STAGES
from peer_atlas_cli.repo_root import find_repo_root


def test_draft_schema_atlas_ingest_enum_matches_program_skeleton() -> None:
    root = find_repo_root()
    path = root / "schemas" / "program_draft.schema.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    enum = data["properties"]["atlas_ingest"]["properties"]["stage"]["enum"]
    assert isinstance(enum, list)
    assert set(enum) == set(ATLAS_INGEST_STAGES)
    assert len(enum) == len(ATLAS_INGEST_STAGES), "duplicate stage in schema enum"
