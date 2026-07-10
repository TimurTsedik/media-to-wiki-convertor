from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from media_to_wiki_convertor.run_events import RunEventWriter


def read_events(raw_data: Path) -> list[dict[str, object]]:
    path = raw_data / "logs" / "run-events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_run_event_writer_appends_jsonl_event_shape(tmp_path: Path) -> None:
    writer = RunEventWriter(tmp_path)
    started_at = datetime(2026, 7, 10, 9, 0, 0, tzinfo=UTC)
    finished_at = datetime(2026, 7, 10, 9, 0, 3, 250000, tzinfo=UTC)

    writer.write(
        stage="transcribe",
        item_id="abc123",
        status="success",
        started_at=started_at,
        finished_at=finished_at,
        message="transcribed abc123",
    )

    assert read_events(tmp_path) == [
        {
            "timestamp": "2026-07-10T09:00:03.250000+00:00",
            "stage": "transcribe",
            "item_id": "abc123",
            "status": "success",
            "started_at": "2026-07-10T09:00:00+00:00",
            "finished_at": "2026-07-10T09:00:03.250000+00:00",
            "elapsed_seconds": 3.25,
            "message": "transcribed abc123",
        }
    ]


def test_run_event_writer_includes_error_for_failed_event(tmp_path: Path) -> None:
    writer = RunEventWriter(tmp_path)
    started_at = datetime(2026, 7, 10, 9, 0, 0, tzinfo=UTC)
    finished_at = datetime(2026, 7, 10, 9, 0, 1, tzinfo=UTC)

    writer.write(
        stage="extract-knowledge",
        item_id="abc123/chunk-0001",
        status="failed",
        started_at=started_at,
        finished_at=finished_at,
        message="knowledge failed abc123/chunk-0001",
        error="boom",
    )

    event = read_events(tmp_path)[0]
    assert event["status"] == "failed"
    assert event["error"] == "boom"
    assert event["elapsed_seconds"] == 1.0
