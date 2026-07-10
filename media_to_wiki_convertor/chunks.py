from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable

from media_to_wiki_convertor.manifest import VideoRecord
from media_to_wiki_convertor.transcription import transcript_paths


@dataclass(frozen=True)
class Chunk:
    index: int
    start: float | None
    end: float | None
    segment_count: int
    text: str
    chunking_mode: str = "time"


@dataclass(frozen=True)
class ChunkingResult:
    video_id: str
    output_dir: Path
    created: int
    skipped: bool


def format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return ""
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def read_transcript_segments(transcript_path: Path) -> list[dict[str, float | str | None]]:
    payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    segments: list[dict[str, float | str | None]] = []

    for raw_segment in payload.get("segments", []):
        text = str(raw_segment.get("text", "")).strip()
        if not text:
            continue
        start = raw_segment.get("start")
        end = raw_segment.get("end")
        segments.append(
            {
                "start": None if start is None else float(start),
                "end": None if end is None else float(end),
                "text": text,
            }
        )

    return segments


def transcript_chunking_mode(segments: list[dict[str, Any]]) -> str:
    for segment in segments:
        if segment.get("start") is None or segment.get("end") is None:
            return "text"
    return "time"


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


def chunk_untimed_segments(
    segments: list[dict[str, Any]],
    chunk_words: int,
    overlap_words: int,
) -> list[Chunk]:
    if chunk_words <= 0:
        raise ValueError("chunk_seconds must be positive")
    if overlap_words < 0:
        raise ValueError("overlap_seconds must not be negative")
    if overlap_words >= chunk_words:
        raise ValueError("overlap_seconds must be smaller than chunk_seconds")

    words = " ".join(str(segment["text"]).strip() for segment in segments).split()
    if not words:
        return []

    chunks: list[Chunk] = []
    step_words = chunk_words - overlap_words
    start_index = 0
    while start_index < len(words):
        selected_words = words[start_index : start_index + chunk_words]
        chunks.append(
            Chunk(
                index=len(chunks) + 1,
                start=None,
                end=None,
                segment_count=len(selected_words),
                text=" ".join(selected_words),
                chunking_mode="text",
            )
        )
        if start_index + chunk_words >= len(words):
            break
        start_index += step_words

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
    transcript_path = transcript_paths(raw_data, record.video_id).json_path
    if not transcript_path.exists():
        existing_count = existing_matching_chunk_count(output_dir, chunk_seconds, overlap_seconds)
        if existing_count:
            return ChunkingResult(
                video_id=record.video_id,
                output_dir=output_dir,
                created=existing_count,
                skipped=True,
            )
        raise FileNotFoundError(f"Missing transcript JSON for {record.video_id}: {transcript_path}")

    if on_progress is not None:
        on_progress(f"read transcript json: {transcript_path}")
    segments = read_transcript_segments(transcript_path)
    chunking_mode = transcript_chunking_mode(segments)

    existing_count = existing_matching_chunk_count(
        output_dir,
        chunk_seconds,
        overlap_seconds,
        chunking_mode,
    )
    if existing_count:
        return ChunkingResult(
            video_id=record.video_id,
            output_dir=output_dir,
            created=existing_count,
            skipped=True,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    for stale_path in [*output_dir.glob("*.json"), *output_dir.glob("*.md")]:
        stale_path.unlink()

    if on_progress is not None:
        on_progress(f"segments loaded: {len(segments)}")
        on_progress(
            f"split windows: chunking_mode={chunking_mode}, "
            f"chunk_seconds={chunk_seconds}, overlap_seconds={overlap_seconds}"
        )
    if chunking_mode == "text":
        chunks = chunk_untimed_segments(
            segments,
            chunk_words=chunk_seconds,
            overlap_words=overlap_seconds,
        )
    else:
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
        "chunking_mode": chunk.chunking_mode,
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
            f"start: {format_seconds(chunk.start) or 'unknown'}",
            f"end: {format_seconds(chunk.end) or 'unknown'}",
            f"segment_count: {chunk.segment_count}",
            f"chunking_mode: {chunk.chunking_mode}",
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
    chunking_mode: str = "time",
) -> int:
    if not output_dir.exists():
        return 0

    json_paths = sorted(output_dir.glob("*.json"))
    if not json_paths:
        return 0

    expected_names = [f"{index:04d}.json" for index in range(1, len(json_paths) + 1)]
    if [path.name for path in json_paths] != expected_names:
        return 0

    for json_path in json_paths:
        md_path = json_path.with_suffix(".md")
        if not md_path.exists() or md_path.stat().st_size == 0:
            return 0
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0

        if str(payload.get("chunk_id", "")) != json_path.stem:
            return 0
        if payload.get("chunk_seconds") != chunk_seconds:
            return 0
        if payload.get("overlap_seconds") != overlap_seconds:
            return 0
        if payload.get("chunking_mode", "time") != chunking_mode:
            return 0
        if not str(payload.get("text", "")).strip():
            return 0

    return len(json_paths)


def count_existing_chunks(raw_data: Path) -> int:
    chunks_dir = raw_data / "chunks"
    if not chunks_dir.exists():
        return 0
    return sum(1 for path in chunks_dir.glob("*/*.json") if path.is_file() and path.stat().st_size > 0)
