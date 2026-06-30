from pathlib import Path

from larchenko_kb.manifest import VideoRecord
from larchenko_kb.transcription import (
    Segment,
    count_existing_transcripts,
    format_srt,
    transcribe_record,
    transcript_paths,
)


def make_record() -> VideoRecord:
    return VideoRecord(
        video_id="abc123",
        path="/videos/lesson.mp4",
        title="lesson",
        extension=".mp4",
        size_bytes=42,
        modified_at="2026-06-30T00:00:00+00:00",
    )


def test_transcript_paths_use_video_id(tmp_path: Path) -> None:
    paths = transcript_paths(tmp_path, "abc123")

    assert paths.json_path == tmp_path / "transcripts" / "abc123.json"
    assert paths.txt_path == tmp_path / "transcripts" / "abc123.txt"
    assert paths.srt_path == tmp_path / "transcripts" / "abc123.srt"


def test_format_srt_writes_timestamps() -> None:
    output = format_srt([Segment(start=1.25, end=3.5, text="Привет")])

    assert output == "1\n00:00:01,250 --> 00:00:03,500\nПривет\n"


def test_transcribe_record_writes_json_txt_and_srt(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio" / "abc123.wav"
    audio_path.parent.mkdir(parents=True)
    audio_path.write_text("wav", encoding="utf-8")

    def fake_transcriber(path: Path, language: str, model: str) -> list[Segment]:
        assert path == audio_path
        assert language == "ru"
        assert model == "medium"
        return [
            Segment(start=0.0, end=1.5, text="Первый фрагмент."),
            Segment(start=1.5, end=3.0, text="Второй фрагмент."),
        ]

    result = transcribe_record(
        make_record(),
        tmp_path,
        language="ru",
        model="medium",
        transcriber=fake_transcriber,
    )

    assert result.skipped is False
    assert result.paths.txt_path.read_text(encoding="utf-8") == (
        "Первый фрагмент.\nВторой фрагмент.\n"
    )
    assert "00:00:01,500" in result.paths.srt_path.read_text(encoding="utf-8")
    assert '"video_id": "abc123"' in result.paths.json_path.read_text(encoding="utf-8")


def test_transcribe_record_skips_existing_non_empty_outputs(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio" / "abc123.wav"
    audio_path.parent.mkdir(parents=True)
    audio_path.write_text("wav", encoding="utf-8")
    paths = transcript_paths(tmp_path, "abc123")
    paths.json_path.parent.mkdir(parents=True)
    paths.json_path.write_text("{}", encoding="utf-8")
    paths.txt_path.write_text("text", encoding="utf-8")
    paths.srt_path.write_text("srt", encoding="utf-8")
    calls = 0

    def fake_transcriber(path: Path, language: str, model: str) -> list[Segment]:
        nonlocal calls
        calls += 1
        return []

    result = transcribe_record(
        make_record(),
        tmp_path,
        language="ru",
        model="medium",
        transcriber=fake_transcriber,
    )

    assert result.skipped is True
    assert calls == 0


def test_count_existing_transcripts_counts_complete_sets(tmp_path: Path) -> None:
    complete = transcript_paths(tmp_path, "complete")
    complete.json_path.parent.mkdir(parents=True)
    complete.json_path.write_text("{}", encoding="utf-8")
    complete.txt_path.write_text("text", encoding="utf-8")
    complete.srt_path.write_text("srt", encoding="utf-8")
    incomplete = transcript_paths(tmp_path, "incomplete")
    incomplete.json_path.write_text("{}", encoding="utf-8")

    assert count_existing_transcripts(tmp_path) == 1
