from __future__ import annotations

import argparse
from pathlib import Path

from larchenko_kb.audio import extract_audio_for_record, has_ffmpeg
from larchenko_kb.config import PipelineConfig, load_config
from larchenko_kb.manifest import (
    build_video_record,
    iter_video_files,
    manifest_path,
    read_video_path_list,
    read_manifest,
    write_manifest,
)


def ensure_raw_layout(raw_data: Path) -> None:
    for relative in [
        "manifest",
        "audio",
        "transcripts",
        "chunks",
        "summaries/chunks",
        "summaries/videos",
        "logs",
    ]:
        (raw_data / relative).mkdir(parents=True, exist_ok=True)


def print_status(config: PipelineConfig) -> None:
    ensure_raw_layout(config.paths.raw_data)
    records = read_manifest(config.paths.raw_data)

    print("Larchenko KB pipeline")
    print(f"video_source: {config.paths.video_source}")
    print(f"raw_data:     {config.paths.raw_data}")
    print(f"vault:        {config.paths.vault}")
    print(f"manifest:     {manifest_path(config.paths.raw_data)}")
    print(f"videos:       {len(records)}")


def discover(config: PipelineConfig, source_override: Path | None = None) -> int:
    ensure_raw_layout(config.paths.raw_data)
    source = source_override or config.paths.video_source
    scanned_dirs = 0

    def report_progress(path: Path) -> None:
        nonlocal scanned_dirs
        scanned_dirs += 1
        if scanned_dirs == 1 or scanned_dirs % 25 == 0:
            print(f"Scanning directory {scanned_dirs}: {path}", flush=True)

    videos = iter_video_files(
        source,
        config.discover.video_extensions,
        config.discover.max_depth,
        on_progress=report_progress,
    )
    records = [build_video_record(path) for path in videos]
    output_path = write_manifest(records, config.paths.raw_data)
    print(f"Discovered {len(records)} video file(s).")
    print(f"Wrote manifest: {output_path}")
    return len(records)


def import_video_list(config: PipelineConfig, list_path: Path, base_dir: Path | None = None) -> int:
    ensure_raw_layout(config.paths.raw_data)
    base = base_dir or config.paths.video_source
    videos = read_video_path_list(list_path, base, config.discover.video_extensions)
    records = [build_video_record(path) for path in videos]
    output_path = write_manifest(records, config.paths.raw_data)
    print(f"Imported {len(records)} video file(s).")
    print(f"Wrote manifest: {output_path}")
    return len(records)


def planned_stage(name: str) -> None:
    print(f"{name} is planned, but not implemented yet.")
    print("Run `python3 -m larchenko_kb discover` first to create the video manifest.")


def extract_audio(config: PipelineConfig) -> int:
    ensure_raw_layout(config.paths.raw_data)
    records = read_manifest(config.paths.raw_data)
    if not records:
        print("No videos in manifest.")
        print("Run `python3 -m larchenko_kb discover` first.")
        return 0
    if not has_ffmpeg():
        print("ffmpeg is not installed or is not available on PATH.")
        print("Install it before running audio extraction, for example: `brew install ffmpeg`.")
        return 1

    extracted = 0
    skipped = 0
    for index, record in enumerate(records, start=1):
        result = extract_audio_for_record(record, config.paths.raw_data)
        if result.skipped:
            skipped += 1
            print(f"[{index}/{len(records)}] skip {record.video_id}: {result.output_path}")
        else:
            extracted += 1
            print(f"[{index}/{len(records)}] extracted {record.video_id}: {result.output_path}")

    print(f"Audio extraction complete: extracted={extracted}, skipped={skipped}")
    return extracted


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="larchenko-kb")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.toml. Defaults to ./config.toml, then ./config.example.toml.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show configured paths and current manifest count.")
    discover_parser = subparsers.add_parser(
        "discover",
        help="Scan the read-only video source and write manifest.",
    )
    discover_parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Override video source directory for this run.",
    )
    import_parser = subparsers.add_parser(
        "import-list",
        help="Build manifest from a text file containing one video path per line.",
    )
    import_parser.add_argument(
        "--file",
        type=Path,
        required=True,
        help="Text file with absolute paths or names relative to --base.",
    )
    import_parser.add_argument(
        "--base",
        type=Path,
        default=None,
        help="Base directory for relative paths. Defaults to configured video_source.",
    )
    subparsers.add_parser("extract-audio", help="Extract mono 16 kHz WAV files with ffmpeg.")
    subparsers.add_parser("transcribe", help="Planned local Whisper transcription stage.")
    subparsers.add_parser("chunk", help="Planned transcript chunking stage.")
    subparsers.add_parser("summarize", help="Planned low-token summarization stage.")
    subparsers.add_parser("build-vault", help="Planned Obsidian Markdown generation stage.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)

    if args.command == "status":
        print_status(config)
        return 0
    if args.command == "discover":
        discover(config, args.source)
        return 0
    if args.command == "import-list":
        import_video_list(config, args.file, args.base)
        return 0
    if args.command == "extract-audio":
        extract_audio(config)
        return 0

    planned_stage(args.command)
    return 0
