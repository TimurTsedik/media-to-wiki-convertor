from pathlib import Path

from larchenko_kb.audio import (
    audio_output_path,
    build_ffmpeg_command,
    count_existing_audio,
    extract_audio_for_record,
)
from larchenko_kb.manifest import VideoRecord


def make_record(path: str = "/videos/lesson.mp4") -> VideoRecord:
    return VideoRecord(
        video_id="abc123",
        path=path,
        title="lesson",
        extension=".mp4",
        size_bytes=42,
        modified_at="2026-06-30T00:00:00+00:00",
    )


def test_audio_output_path_uses_video_id(tmp_path: Path) -> None:
    assert audio_output_path(tmp_path, "abc123") == tmp_path / "audio" / "abc123.wav"


def test_build_ffmpeg_command_extracts_mono_16khz_audio(tmp_path: Path) -> None:
    input_path = Path("/videos/lesson.mp4")
    output_path = tmp_path / "audio" / "abc123.wav"

    command = build_ffmpeg_command(input_path, output_path)

    assert command == [
        "ffmpeg",
        "-y",
        "-i",
        "/videos/lesson.mp4",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_path),
    ]


def test_extract_audio_runs_ffmpeg_when_output_is_missing(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(command: list[str]) -> None:
        calls.append(command)
        Path(command[-1]).write_text("wav", encoding="utf-8")

    result = extract_audio_for_record(make_record(), tmp_path, runner=runner)

    assert result.video_id == "abc123"
    assert result.output_path == tmp_path / "audio" / "abc123.wav"
    assert result.skipped is False
    assert len(calls) == 1


def test_extract_audio_skips_existing_output(tmp_path: Path) -> None:
    output_path = tmp_path / "audio" / "abc123.wav"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("wav", encoding="utf-8")
    calls: list[list[str]] = []

    result = extract_audio_for_record(make_record(), tmp_path, runner=calls.append)

    assert result.output_path == output_path
    assert result.skipped is True
    assert calls == []


def test_extract_audio_rebuilds_empty_output(tmp_path: Path) -> None:
    output_path = tmp_path / "audio" / "abc123.wav"
    output_path.parent.mkdir(parents=True)
    output_path.write_bytes(b"")
    calls: list[list[str]] = []

    def runner(command: list[str]) -> None:
        calls.append(command)
        Path(command[-1]).write_text("wav", encoding="utf-8")

    result = extract_audio_for_record(make_record(), tmp_path, runner=runner)

    assert result.output_path == output_path
    assert result.skipped is False
    assert len(calls) == 1


def test_count_existing_audio_counts_non_empty_outputs(tmp_path: Path) -> None:
    (tmp_path / "audio").mkdir()
    (tmp_path / "audio" / "abc123.wav").write_text("wav", encoding="utf-8")
    (tmp_path / "audio" / "empty.wav").write_bytes(b"")

    assert count_existing_audio(tmp_path) == 1
