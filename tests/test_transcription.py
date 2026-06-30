from pathlib import Path
import wave

from larchenko_kb.manifest import VideoRecord
from larchenko_kb.transcription import (
    Segment,
    count_existing_transcripts,
    format_elapsed,
    format_srt,
    load_pcm16_wav,
    transcribe_records,
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


def make_record_with_id(video_id: str) -> VideoRecord:
    return VideoRecord(
        video_id=video_id,
        path=f"/videos/{video_id}.mp4",
        title=video_id,
        extension=".mp4",
        size_bytes=42,
        modified_at="2026-06-30T00:00:00+00:00",
    )


def write_valid_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes((0).to_bytes(2, "little", signed=True))


def test_transcript_paths_use_video_id(tmp_path: Path) -> None:
    paths = transcript_paths(tmp_path, "abc123")

    assert paths.json_path == tmp_path / "transcripts" / "abc123.json"
    assert paths.txt_path == tmp_path / "transcripts" / "abc123.txt"
    assert paths.srt_path == tmp_path / "transcripts" / "abc123.srt"


def test_format_srt_writes_timestamps() -> None:
    output = format_srt([Segment(start=1.25, end=3.5, text="Привет")])

    assert output == "1\n00:00:01,250 --> 00:00:03,500\nПривет\n"


def test_format_elapsed_uses_hh_mm_ss() -> None:
    assert format_elapsed(3.2) == "00:00:03"
    assert format_elapsed(65.9) == "00:01:05"
    assert format_elapsed(3661.1) == "01:01:01"


def test_load_pcm16_wav_returns_float32_samples(tmp_path: Path) -> None:
    path = tmp_path / "sample.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes((0).to_bytes(2, "little", signed=True))
        wav.writeframes((32767).to_bytes(2, "little", signed=True))

    audio = load_pcm16_wav(path)

    assert audio.dtype.name == "float32"
    assert audio.shape == (2,)
    assert audio[0] == 0
    assert 0.99 < float(audio[1]) <= 1.0


def test_transcribe_record_writes_json_txt_and_srt(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio" / "abc123.wav"
    write_valid_wav(audio_path)

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
    write_valid_wav(audio_path)
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


def test_transcribe_records_continues_after_one_failure(tmp_path: Path) -> None:
    for video_id in ["skip", "fail", "ok"]:
        audio_path = tmp_path / "audio" / f"{video_id}.wav"
        write_valid_wav(audio_path)

    skip_paths = transcript_paths(tmp_path, "skip")
    skip_paths.json_path.parent.mkdir(parents=True)
    skip_paths.json_path.write_text("{}", encoding="utf-8")
    skip_paths.txt_path.write_text("text", encoding="utf-8")
    skip_paths.srt_path.write_text("srt", encoding="utf-8")

    def fake_transcriber(path: Path, language: str, model: str) -> list[Segment]:
        if path.name == "fail.wav":
            raise RuntimeError("temporary timeout")
        return [Segment(start=0, end=1, text=f"done {path.stem}")]

    result = transcribe_records(
        [make_record_with_id("skip"), make_record_with_id("fail"), make_record_with_id("ok")],
        tmp_path,
        language="ru",
        model="medium",
        transcriber=fake_transcriber,
    )

    assert result.created == 1
    assert result.skipped == 1
    assert result.failed == 1
    assert result.failures == [("fail", "temporary timeout")]
    assert transcript_paths(tmp_path, "ok").txt_path.read_text(encoding="utf-8") == "done ok\n"
