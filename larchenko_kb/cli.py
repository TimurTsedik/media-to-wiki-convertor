from __future__ import annotations

import argparse
from pathlib import Path

from larchenko_kb.config import PipelineConfig, load_config
from larchenko_kb.manifest import (
    build_video_record,
    iter_video_files,
    manifest_path,
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


def discover(config: PipelineConfig) -> int:
    ensure_raw_layout(config.paths.raw_data)
    videos = iter_video_files(
        config.paths.video_source,
        config.discover.video_extensions,
        config.discover.max_depth,
    )
    records = [build_video_record(path) for path in videos]
    output_path = write_manifest(records, config.paths.raw_data)
    print(f"Discovered {len(records)} video file(s).")
    print(f"Wrote manifest: {output_path}")
    return len(records)


def planned_stage(name: str) -> None:
    print(f"{name} is planned, but not implemented yet.")
    print("Run `python3 -m larchenko_kb discover` first to create the video manifest.")


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
    subparsers.add_parser("discover", help="Scan the read-only video source and write manifest.")
    subparsers.add_parser("extract-audio", help="Planned ffmpeg audio extraction stage.")
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
        discover(config)
        return 0

    planned_stage(args.command)
    return 0
