from __future__ import annotations

import json
from pathlib import Path

from media_to_wiki_convertor import cli
from media_to_wiki_convertor.cli import build_parser
from media_to_wiki_convertor.config import (
    ChunkingConfig,
    DiscoverConfig,
    LLMConfig,
    PipelineConfig,
    PipelinePaths,
    TranscriptionConfig,
    WikiConfig,
)
from media_to_wiki_convertor.manifest import VideoRecord, write_manifest


def test_import_transcript_parser_accepts_required_arguments() -> None:
    args = build_parser().parse_args(
        [
            "import-transcript",
            "--video-id",
            "abc123",
            "--file",
            "transcript.txt",
            "--force",
        ]
    )

    assert args.command == "import-transcript"
    assert args.video_id == "abc123"
    assert str(args.file) == "transcript.txt"
    assert args.force is True


def make_config(tmp_path: Path) -> PipelineConfig:
    return PipelineConfig(
        paths=PipelinePaths(
            video_source=tmp_path / "videos",
            raw_data=tmp_path / "raw-data",
            vault=tmp_path / "vault",
        ),
        discover=DiscoverConfig(video_extensions=(".mp4",), max_depth=1),
        transcription=TranscriptionConfig(engine="mlx-whisper", model="tiny", language="en"),
        llm=LLMConfig(provider="openai", model="gpt-test"),
        wiki=WikiConfig(language="en"),
        chunking=ChunkingConfig(chunk_minutes=10, overlap_seconds=120),
    )


def test_transcribe_writes_failed_run_event(tmp_path: Path, monkeypatch) -> None:
    config = make_config(tmp_path)
    record = VideoRecord(
        video_id="abc123",
        path=str(tmp_path / "videos" / "lesson.mp4"),
        title="lesson",
        extension=".mp4",
        size_bytes=42,
        modified_at="2026-07-10T00:00:00+00:00",
    )
    write_manifest([record], config.paths.raw_data)

    def fail_transcribe(*args, **kwargs):
        raise RuntimeError("transcription exploded")

    monkeypatch.setattr(cli, "transcribe_record", fail_transcribe)

    assert cli.transcribe(config) == 1

    events_path = config.paths.raw_data / "logs" / "run-events.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]

    assert [event["status"] for event in events] == ["started", "failed"]
    assert events[0]["stage"] == "transcribe"
    assert events[0]["item_id"] == "abc123"
    assert events[1]["stage"] == "transcribe"
    assert events[1]["item_id"] == "abc123"
    assert events[1]["error"] == "transcription exploded"
    assert events[1]["elapsed_seconds"] >= 0


def test_build_vault_writes_failed_run_event_for_unexpected_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = make_config(tmp_path)

    def fail_build_vault(*args, **kwargs):
        raise RuntimeError("vault exploded")

    monkeypatch.setattr(cli, "build_obsidian_vault", fail_build_vault)

    assert cli.build_vault(config) == 1

    events_path = config.paths.raw_data / "logs" / "run-events.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]

    assert [event["status"] for event in events] == ["started", "failed"]
    assert events[1]["stage"] == "build-vault"
    assert events[1]["item_id"] == "vault"
    assert events[1]["error"] == "vault exploded"
