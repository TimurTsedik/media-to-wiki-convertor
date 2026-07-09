from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable

from video_kb.manifest import VideoRecord
from video_kb.transcription import transcript_paths


@dataclass(frozen=True)
class Chunk:
    index: int
    start: float
    end: float
    segment_count: int
    text: str


@dataclass(frozen=True)
class ChunkingResult:
    video_id: str
    output_dir: Path
    created: int
    skipped: bool


def format_seconds(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def read_transcript_segments(transcript_path: Path) -> list[dict[str, float | str]]:
    payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    segments: list[dict[str, float | str]] = []

    for raw_segment in payload.get("segments", []):
        text = str(raw_segment.get("text", "")).strip()
        if not text:
            continue
        segments.append(
            {
                "start": float(raw_segment["start"]),
                "end": float(raw_segment["end"]),
                "text": text,
            }
        )

    return segments


def chunk_segments(
    segments: list[dict[str, Any]],
    chunk_seconds: int,
    overlap_seconds: int,
) -> list[Chunk]:
    if chunk_seconds <= 0:
        raise ValueError("chunk_seconds must be positive")
    if overlap_seconds < 0:
        raise ValueError("overlap_seconds must not be negative")
    if overlap_seconds >= chunk_seconds:
        raise ValueError("overlap_seconds must be smaller than chunk_seconds")
    if not segments:
        return []

    sorted_segments = sorted(segments, key=lambda segment: float(segment["start"]))
    first_start = float(sorted_segments[0]["start"])
    last_end = max(float(segment["end"]) for segment in sorted_segments)
    step_seconds = chunk_seconds - overlap_seconds

    chunks: list[Chunk] = []
    window_start = first_start

    while window_start < last_end:
        window_end = window_start + chunk_seconds
        selected = [
            segment
            for segment in sorted_segments
            if float(segment["start"]) < window_end and float(segment["end"]) > window_start
        ]

        if selected:
            text = "\n".join(str(segment["text"]).strip() for segment in selected)
            chunks.append(
                Chunk(
                    index=len(chunks) + 1,
                    start=float(selected[0]["start"]),
                    end=float(selected[-1]["end"]),
                    segment_count=len(selected),
                    text=text,
                )
            )

        if window_end >= last_end:
            break
        window_start += step_seconds

    return chunks


def chunk_output_dir(raw_data: Path, video_id: str) -> Path:
    return raw_data / "chunks" / video_id


def chunk_transcript_record(
    record: VideoRecord,
    raw_data: Path,
    chunk_seconds: int,
    overlap_seconds: int,
    on_progress: Callable[[str], None] | None = None,
) -> ChunkingResult:
    output_dir = chunk_output_dir(raw_data, record.video_id)
    existing_count = existing_matching_chunk_count(output_dir, chunk_seconds, overlap_seconds)
    if existing_count:
        return ChunkingResult(
            video_id=record.video_id,
            output_dir=output_dir,
            created=existing_count,
            skipped=True,
        )

    transcript_path = transcript_paths(raw_data, record.video_id).json_path
    if not transcript_path.exists():
        raise FileNotFoundError(f"Missing transcript JSON for {record.video_id}: {transcript_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    for stale_path in [*output_dir.glob("*.json"), *output_dir.glob("*.md")]:
        stale_path.unlink()

    if on_progress is not None:
        on_progress(f"read transcript json: {transcript_path}")
    segments = read_transcript_segments(transcript_path)
    if on_progress is not None:
        on_progress(f"segments loaded: {len(segments)}")
        on_progress(f"split windows: chunk_seconds={chunk_seconds}, overlap_seconds={overlap_seconds}")
    chunks = chunk_segments(
        segments,
        chunk_seconds=chunk_seconds,
        overlap_seconds=overlap_seconds,
    )
    if on_progress is not None:
        on_progress(f"chunks planned: {len(chunks)}")

    for chunk in chunks:
        write_chunk_files(record, output_dir, chunk, chunk_seconds, overlap_seconds)
    if on_progress is not None:
        on_progress(f"chunks written: {output_dir}")

    return ChunkingResult(
        video_id=record.video_id,
        output_dir=output_dir,
        created=len(chunks),
        skipped=False,
    )


def write_chunk_files(
    record: VideoRecord,
    output_dir: Path,
    chunk: Chunk,
    chunk_seconds: int,
    overlap_seconds: int,
) -> None:
    chunk_id = f"{chunk.index:04d}"
    payload = {
        "video_id": record.video_id,
        "title": record.title,
        "source_path": record.path,
        "chunk_id": chunk_id,
        "index": chunk.index,
        "start": chunk.start,
        "end": chunk.end,
        "start_hms": format_seconds(chunk.start),
        "end_hms": format_seconds(chunk.end),
        "segment_count": chunk.segment_count,
        "chunk_seconds": chunk_seconds,
        "overlap_seconds": overlap_seconds,
        "text": chunk.text,
    }
    json_path = output_dir / f"{chunk_id}.json"
    md_path = output_dir / f"{chunk_id}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(format_chunk_markdown(record, chunk, chunk_id), encoding="utf-8")


def format_chunk_markdown(record: VideoRecord, chunk: Chunk, chunk_id: str) -> str:
    return "\n".join(
        [
            "---",
            f"source_video: {record.video_id}",
            f"chunk_id: {chunk_id}",
            f"start: {format_seconds(chunk.start)}",
            f"end: {format_seconds(chunk.end)}",
            f"segment_count: {chunk.segment_count}",
            "---",
            "",
            f"# {record.title} - chunk {chunk_id}",
            "",
            chunk.text,
            "",
        ]
    )


def existing_matching_chunk_count(
    output_dir: Path,
    chunk_seconds: int,
    overlap_seconds: int,
) -> int:
    if not output_dir.exists():
        return 0

    json_paths = sorted(output_dir.glob("*.json"))
    if not json_paths:
        return 0

    try:
        first_payload = json.loads(json_paths[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0

    if first_payload.get("chunk_seconds") != chunk_seconds:
        return 0
    if first_payload.get("overlap_seconds") != overlap_seconds:
        return 0

    return len(json_paths)


def count_existing_chunks(raw_data: Path) -> int:
    chunks_dir = raw_data / "chunks"
    if not chunks_dir.exists():
        return 0
    return sum(1 for path in chunks_dir.glob("*/*.json") if path.is_file() and path.stat().st_size > 0)
