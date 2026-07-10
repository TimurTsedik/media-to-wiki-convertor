from pathlib import Path

from media_to_wiki_convertor.chunks import (
    Chunk,
    chunk_segments,
    chunk_transcript_record,
    count_existing_chunks,
    format_seconds,
    read_transcript_segments,
)
from media_to_wiki_convertor.manifest import VideoRecord


def make_record(video_id: str = "abc123") -> VideoRecord:
    return VideoRecord(
        video_id=video_id,
        path=f"/videos/{video_id}.mp4",
        title="Lesson One",
        extension=".mp4",
        size_bytes=42,
        modified_at="2026-06-30T00:00:00+00:00",
    )


def test_chunk_segments_uses_time_window_with_overlap() -> None:
    segments = [
        {"start": 0.0, "end": 60.0, "text": "zero"},
        {"start": 60.0, "end": 120.0, "text": "one"},
        {"start": 120.0, "end": 180.0, "text": "two"},
        {"start": 180.0, "end": 240.0, "text": "three"},
        {"start": 240.0, "end": 300.0, "text": "four"},
    ]

    chunks = chunk_segments(segments, chunk_seconds=180, overlap_seconds=60)

    assert chunks == [
        Chunk(index=1, start=0.0, end=180.0, segment_count=3, text="zero\none\ntwo"),
        Chunk(index=2, start=120.0, end=300.0, segment_count=3, text="two\nthree\nfour"),
    ]


def test_chunk_segments_keeps_short_transcript_as_one_chunk() -> None:
    segments = [
        {"start": 10.0, "end": 20.0, "text": "hello"},
        {"start": 20.0, "end": 25.0, "text": "world"},
    ]

    chunks = chunk_segments(segments, chunk_seconds=600, overlap_seconds=120)

    assert chunks == [Chunk(index=1, start=10.0, end=25.0, segment_count=2, text="hello\nworld")]


def test_format_seconds_uses_hh_mm_ss() -> None:
    assert format_seconds(0) == "00:00:00"
    assert format_seconds(65.9) == "00:01:05"
    assert format_seconds(3661.1) == "01:01:01"


def test_read_transcript_segments_loads_whisper_json(tmp_path: Path) -> None:
    transcript_path = tmp_path / "transcripts" / "abc123.json"
    transcript_path.parent.mkdir(parents=True)
    transcript_path.write_text(
        """
{
  "segments": [
    {"start": 0.0, "end": 1.5, "text": " Привет "},
    {"start": 1.5, "end": 3.0, "text": ""}
  ]
}
""".strip(),
        encoding="utf-8",
    )

    assert read_transcript_segments(transcript_path) == [
        {"start": 0.0, "end": 1.5, "text": "Привет"}
    ]


def test_chunk_transcript_record_writes_json_and_markdown(tmp_path: Path) -> None:
    transcript_path = tmp_path / "transcripts" / "abc123.json"
    transcript_path.parent.mkdir(parents=True)
    transcript_path.write_text(
        """
{
  "segments": [
    {"start": 0.0, "end": 60.0, "text": "Первый"},
    {"start": 60.0, "end": 120.0, "text": "Второй"},
    {"start": 120.0, "end": 180.0, "text": "Третий"},
    {"start": 180.0, "end": 240.0, "text": "Четвертый"}
  ]
}
""".strip(),
        encoding="utf-8",
    )

    result = chunk_transcript_record(
        make_record(),
        tmp_path,
        chunk_seconds=180,
        overlap_seconds=60,
    )

    assert result.video_id == "abc123"
    assert result.created == 2
    assert result.output_dir == tmp_path / "chunks" / "abc123"
    first_json = result.output_dir / "0001.json"
    first_md = result.output_dir / "0001.md"
    assert '"video_id": "abc123"' in first_json.read_text(encoding="utf-8")
    assert '"overlap_seconds": 60' in first_json.read_text(encoding="utf-8")
    assert '"chunking_mode": "time"' in first_json.read_text(encoding="utf-8")
    markdown = first_md.read_text(encoding="utf-8")
    assert "# Lesson One - chunk 0001" in markdown
    assert "source_video: abc123" in markdown
    assert "start: 00:00:00" in markdown
    assert "end: 00:03:00" in markdown
    assert "Первый\nВторой\nТретий" in markdown


def test_chunk_transcript_record_chunks_untimed_transcript_by_text_with_overlap(tmp_path: Path) -> None:
    transcript_path = tmp_path / "transcripts" / "abc123.json"
    transcript_path.parent.mkdir(parents=True)
    transcript_path.write_text(
        """
{
  "timing": "untimed",
  "segments": [
    {"start": null, "end": null, "text": "alpha beta gamma delta"},
    {"start": null, "end": null, "text": "epsilon zeta eta theta"}
  ]
}
""".strip(),
        encoding="utf-8",
    )

    result = chunk_transcript_record(
        make_record(),
        tmp_path,
        chunk_seconds=3,
        overlap_seconds=1,
    )

    assert result.created == 4
    first_payload = (result.output_dir / "0001.json").read_text(encoding="utf-8")
    second_payload = (result.output_dir / "0002.json").read_text(encoding="utf-8")
    assert '"chunking_mode": "text"' in first_payload
    assert '"start": null' in first_payload
    assert '"end_hms": ""' in first_payload
    assert '"text": "alpha beta gamma"' in first_payload
    assert '"text": "gamma delta epsilon"' in second_payload
    markdown = (result.output_dir / "0001.md").read_text(encoding="utf-8")
    assert "start: unknown" in markdown
    assert "end: unknown" in markdown


def test_chunk_transcript_record_skips_existing_chunks_with_same_settings(tmp_path: Path) -> None:
    output_dir = tmp_path / "chunks" / "abc123"
    output_dir.mkdir(parents=True)
    (output_dir / "0001.json").write_text(
        """
{
  "chunk_seconds": 600,
  "overlap_seconds": 120,
  "text": "existing"
}
""".strip(),
        encoding="utf-8",
    )

    result = chunk_transcript_record(
        make_record(),
        tmp_path,
        chunk_seconds=600,
        overlap_seconds=120,
    )

    assert result.skipped is True
    assert result.created == 1
    assert (output_dir / "0001.json").read_text(encoding="utf-8").count("existing") == 1


def test_count_existing_chunks_counts_json_files(tmp_path: Path) -> None:
    (tmp_path / "chunks" / "abc123").mkdir(parents=True)
    (tmp_path / "chunks" / "abc123" / "0001.json").write_text("{}", encoding="utf-8")
    (tmp_path / "chunks" / "abc123" / "0001.md").write_text("text", encoding="utf-8")
    (tmp_path / "chunks" / "def456").mkdir()
    (tmp_path / "chunks" / "def456" / "0001.json").write_text("{}", encoding="utf-8")

    assert count_existing_chunks(tmp_path) == 2
