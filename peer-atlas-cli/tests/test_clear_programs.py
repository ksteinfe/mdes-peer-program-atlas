"""clear_all_programs."""

from __future__ import annotations

import json

from peer_atlas_cli.corpus_io import clear_all_programs, load_corpus, programs_list


def test_clear_all_programs_saves_snapshot_and_empties(tmp_path) -> None:
    root = tmp_path / "repo"
    corpus_dir = root / "corpus"
    corpus_dir.mkdir(parents=True)
    path = corpus_dir / "programs.json"
    data = {
        "corpus_metadata": {"version": 1, "description": "t"},
        "programs": [{"program_id": "only_one", "base_url": "https://x.edu/"}],
    }
    path.write_text(json.dumps(data), encoding="utf-8")

    n, archive = clear_all_programs(root)
    assert n == 1
    assert archive is not None
    assert archive.is_file()
    assert "programs.archive." in archive.name

    after = load_corpus(root)
    assert programs_list(after) == []


def test_clear_all_programs_no_archive_when_empty(tmp_path) -> None:
    root = tmp_path / "repo"
    corpus_dir = root / "corpus"
    corpus_dir.mkdir(parents=True)
    path = corpus_dir / "programs.json"
    path.write_text(
        json.dumps({"corpus_metadata": {"version": 1}, "programs": []}),
        encoding="utf-8",
    )
    n, archive = clear_all_programs(root)
    assert n == 0
    assert archive is None
    assert programs_list(load_corpus(root)) == []
