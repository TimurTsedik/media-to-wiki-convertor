from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Callable
import wave

from larchenko_kb.audio import audio_is_valid, audio_output_path, is_non_empty_file
from larchenko_kb.manifest import VideoRecord


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptPaths:
    json_path: Path
    txt_path: Path
    srt_path: Path


@dataclass(frozen=True)
class TranscriptionResult:
    video_id: str
    audio_path: Path
    paths: TranscriptPaths
    skipped: bool


@dataclass(frozen=True)
class TranscriptionBatchResult:
    created: int
    skipped: int
    failed: int
    failures: list[tuple[str, str]]


Transcriber = Callable[[Path, str, str], list[Segment]]


def transcript_paths(raw_data: Path, video_id: str) -> TranscriptPaths:
    transcript_dir = raw_data / "transcripts"
    return TranscriptPaths(
        json_path=transcript_dir / f"{video_id}.json",
        txt_path=transcript_dir / f"{video_id}.txt",
        srt_path=transcript_dir / f"{video_id}.srt",
    )


def transcript_complete(paths: TranscriptPaths) -> bool:
    return (
        is_non_empty_file(paths.json_path)
        and is_non_empty_file(paths.txt_path)
        and is_non_empty_file(paths.srt_path)
    )


def count_existing_transcripts(raw_data: Path) -> int:
    transcript_dir = raw_data / "transcripts"
    if not transcript_dir.exists():
        return 0

    count = 0
    for json_path in transcript_dir.glob("*.json"):
        paths = transcript_paths(raw_data, json_path.stem)
        if transcript_complete(paths):
            count += 1
    return count


def format_timestamp(seconds: float) -> str:
    milliseconds_total = round(seconds * 1000)
    hours, remainder = divmod(milliseconds_total, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def format_elapsed(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_srt(segments: list[Segment]) -> str:
    blocks: list[str] = []
    for index, segment in enumerate(segments, start=1):
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_timestamp(segment.start)} --> {format_timestamp(segment.end)}",
                    segment.text.strip(),
                ]
            )
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def default_mlx_transcriber(audio_path: Path, language: str, model: str) -> list[Segment]:
    try:
        import mlx_whisper
    except ImportError as exc:
        raise RuntimeError(
            "mlx-whisper is not installed. Install it with: "
            "python3 -m pip install mlx-whisper"
        ) from exc

    print(f"  loading wav into memory: {audio_path}", flush=True)
    audio = load_pcm16_wav(audio_path)
    print(f"  wav loaded: samples={audio.shape[0]}", flush=True)
    print(f"  running mlx-whisper model={model} language={language}", flush=True)
    result = mlx_whisper.transcribe(audio, path_or_hf_repo=model, language=language)
    print(f"  model finished: segments={len(result.get('segments', []))}", flush=True)
    return [
        Segment(
            start=float(segment["start"]),
            end=float(segment["end"]),
            text=str(segment["text"]).strip(),
        )
        for segment in result.get("segments", [])
    ]


def load_pcm16_wav(audio_path: Path) -> np.ndarray:
    import numpy as np

    with wave.open(str(audio_path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16000:
            raise ValueError(f"Expected mono 16 kHz PCM16 WAV: {audio_path}")
        frames = wav.readframes(wav.getnframes())

    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32)
    return samples / 32768.0


def write_transcript_files(
    record: VideoRecord,
    paths: TranscriptPaths,
    segments: list[Segment],
    language: str,
    model: str,
) -> None:
    paths.json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "video_id": record.video_id,
        "title": record.title,
        "source_path": record.path,
        "language": language,
        "model": model,
        "segments": [asdict(segment) for segment in segments],
    }
    paths.json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths.txt_path.write_text(
        "".join(f"{segment.text.strip()}\n" for segment in segments if segment.text.strip()),
        encoding="utf-8",
    )
    paths.srt_path.write_text(format_srt(segments), encoding="utf-8")


def append_transcription_log(raw_data: Path, message: str) -> None:
    log_path = raw_data / "logs" / "transcribe.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(message.rstrip() + "\n")


def transcribe_record(
    record: VideoRecord,
    raw_data: Path,
    language: str,
    model: str,
    transcriber: Transcriber = default_mlx_transcriber,
) -> TranscriptionResult:
    audio_path = audio_output_path(raw_data, record.video_id)
    paths = transcript_paths(raw_data, record.video_id)

    if transcript_complete(paths):
        append_transcription_log(raw_data, f"skip {record.video_id} {paths.json_path}")
        return TranscriptionResult(
            video_id=record.video_id,
            audio_path=audio_path,
            paths=paths,
            skipped=True,
        )

    if not is_non_empty_file(audio_path):
        raise FileNotFoundError(f"Missing audio file for {record.video_id}: {audio_path}")
    if not audio_is_valid(audio_path):
        raise ValueError(f"Invalid audio file for {record.video_id}: {audio_path}")

    append_transcription_log(raw_data, f"run {record.video_id} {audio_path}")
    segments = transcriber(audio_path, language, model)
    write_transcript_files(record, paths, segments, language, model)
    return TranscriptionResult(
        video_id=record.video_id,
        audio_path=audio_path,
        paths=paths,
        skipped=False,
    )


def transcribe_records(
    records: list[VideoRecord],
    raw_data: Path,
    language: str,
    model: str,
    transcriber: Transcriber = default_mlx_transcriber,
) -> TranscriptionBatchResult:
    created = 0
    skipped = 0
    failures: list[tuple[str, str]] = []

    for record in records:
        try:
            result = transcribe_record(
                record,
                raw_data,
                language=language,
                model=model,
                transcriber=transcriber,
            )
        except Exception as exc:
            message = str(exc)
            failures.append((record.video_id, message))
            append_transcription_log(raw_data, f"fail {record.video_id} {message}")
            continue

        if result.skipped:
            skipped += 1
        else:
            created += 1

    return TranscriptionBatchResult(
        created=created,
        skipped=skipped,
        failed=len(failures),
        failures=failures,
    )
