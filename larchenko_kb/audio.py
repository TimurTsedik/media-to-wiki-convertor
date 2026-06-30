from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

from larchenko_kb.manifest import VideoRecord


@dataclass(frozen=True)
class AudioExtractionResult:
    video_id: str
    input_path: Path
    output_path: Path
    skipped: bool


def audio_output_path(raw_data: Path, video_id: str) -> Path:
    return raw_data / "audio" / f"{video_id}.wav"


def is_non_empty_file(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def count_existing_audio(raw_data: Path) -> int:
    audio_dir = raw_data / "audio"
    if not audio_dir.exists():
        return 0
    return sum(1 for path in audio_dir.glob("*.wav") if is_non_empty_file(path))


def build_ffmpeg_command(input_path: Path, output_path: Path) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_path),
    ]


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def default_runner(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True)


def append_audio_log(raw_data: Path, message: str) -> None:
    log_path = raw_data / "logs" / "extract-audio.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(message.rstrip() + "\n")


def extract_audio_for_record(
    record: VideoRecord,
    raw_data: Path,
    runner=default_runner,
) -> AudioExtractionResult:
    input_path = Path(record.path)
    output_path = audio_output_path(raw_data, record.video_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if is_non_empty_file(output_path):
        append_audio_log(raw_data, f"skip {record.video_id} {output_path}")
        return AudioExtractionResult(
            video_id=record.video_id,
            input_path=input_path,
            output_path=output_path,
            skipped=True,
        )

    command = build_ffmpeg_command(input_path, output_path)
    append_audio_log(raw_data, f"run {record.video_id} {' '.join(command)}")
    runner(command)
    return AudioExtractionResult(
        video_id=record.video_id,
        input_path=input_path,
        output_path=output_path,
        skipped=False,
    )
