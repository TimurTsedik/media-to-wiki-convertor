from __future__ import annotations

import json
from pathlib import Path

from media_to_wiki_convertor.artifacts import validate_artifacts


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_validate_artifacts_accepts_complete_resume_outputs(tmp_path: Path) -> None:
    write_json(
        tmp_path / "chunks" / "abc123" / "0001.json",
        {
            "video_id": "abc123",
            "chunk_id": "0001",
            "chunk_seconds": 600,
            "overlap_seconds": 120,
            "chunking_mode": "time",
            "text": "chunk text",
        },
    )
    (tmp_path / "chunks" / "abc123" / "0001.md").write_text("chunk note", encoding="utf-8")
    write_json(
        tmp_path / "extracted_knowledge" / "abc123" / "0001.json",
        {"source": {"video_id": "abc123", "chunk_id": "0001"}},
    )

    assert validate_artifacts(tmp_path) == []


def test_validate_artifacts_reports_partial_chunks_and_bad_knowledge(tmp_path: Path) -> None:
    write_json(
        tmp_path / "chunks" / "abc123" / "0001.json",
        {
            "video_id": "abc123",
            "chunk_id": "9999",
            "chunk_seconds": 600,
            "overlap_seconds": 120,
            "chunking_mode": "time",
            "text": "",
        },
    )
    write_json(
        tmp_path / "extracted_knowledge" / "abc123" / "0001.json",
        {"source": {"video_id": "abc123", "chunk_id": "9999"}},
    )
    draft_path = tmp_path / "draft_articles" / "broken.md"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text("body without heading", encoding="utf-8")
    course_path = tmp_path / "course_materials" / "broken.md"
    course_path.parent.mkdir(parents=True, exist_ok=True)
    course_path.write_text("body without heading", encoding="utf-8")

    issues = validate_artifacts(tmp_path)
    messages = [issue.message for issue in issues]

    assert "Missing chunk markdown sidecar" in messages
    assert "Chunk id does not match filename" in messages
    assert "Chunk text is empty" in messages
    assert "Knowledge source does not match path" in messages
    assert messages.count("Markdown artifact is missing a top-level heading") == 2
