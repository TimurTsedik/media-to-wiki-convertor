from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Callable
import unicodedata


@dataclass(frozen=True)
class VideoRecord:
    video_id: str
    path: str
    title: str
    extension: str
    size_bytes: int
    modified_at: str


MediaRecord = VideoRecord


def manifest_path(raw_data: Path) -> Path:
    return raw_data / "manifest" / "videos.jsonl"


def stable_video_id(path: Path) -> str:
    return hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]


def stable_media_id(path: Path) -> str:
    return stable_video_id(path)


def iter_video_files(
    source: Path,
    extensions: tuple[str, ...],
    max_depth: int,
    on_progress: Callable[[Path], None] | None = None,
) -> list[Path]:
    if not source.exists():
        return []

    matches: list[Path] = []
    pending: list[tuple[Path, int]] = [(source, 0)]
    normalized_extensions = {ext.lower() for ext in extensions}

    while pending:
        current_dir, depth = pending.pop()
        if on_progress is not None:
            on_progress(current_dir)

        try:
            with os.scandir(current_dir) as entries:
                current_entries = sorted(entries, key=lambda entry: entry.name.casefold())
        except OSError:
            continue

        for entry in current_entries:
            path = Path(entry.path)
            try:
                if entry.is_file(follow_symlinks=False):
                    if depth + 1 <= max_depth and path.suffix.lower() in normalized_extensions:
                        matches.append(path)
                elif entry.is_dir(follow_symlinks=False) and depth < max_depth:
                    pending.append((path, depth + 1))
            except OSError:
                continue

    return sorted(matches, key=lambda item: str(item).casefold())


def iter_media_files(
    source: Path,
    extensions: tuple[str, ...],
    max_depth: int,
    on_progress: Callable[[Path], None] | None = None,
) -> list[Path]:
    return iter_video_files(source, extensions, max_depth, on_progress=on_progress)


def read_video_path_list(
    list_path: Path,
    base_dir: Path,
    extensions: tuple[str, ...],
) -> list[Path]:
    normalized_extensions = {ext.lower() for ext in extensions}
    paths: list[Path] = []

    for raw_line in list_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        path = path_from_list_line(line, base_dir)

        if path.suffix.lower() in normalized_extensions:
            paths.append(path)

    return paths


def read_media_path_list(
    list_path: Path,
    base_dir: Path,
    extensions: tuple[str, ...],
) -> list[Path]:
    return read_video_path_list(list_path, base_dir, extensions)


def path_from_list_line(line: str, base_dir: Path) -> Path:
    path = Path(line)
    if path.is_absolute():
        return path

    candidate = base_dir / path
    if candidate.exists():
        return candidate

    normalized_line = strip_leading_icon(line)
    if normalized_line != line:
        return base_dir / normalized_line

    return candidate


def strip_leading_icon(line: str) -> str:
    stripped = line.lstrip()
    while stripped and unicodedata.category(stripped[0]) == "Co":
        stripped = stripped[1:].lstrip()
    return stripped


def build_video_record(path: Path) -> VideoRecord:
    stat = path.stat()
    return VideoRecord(
        video_id=stable_video_id(path),
        path=str(path),
        title=path.stem,
        extension=path.suffix.lower(),
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
    )


def build_media_record(path: Path) -> MediaRecord:
    return build_video_record(path)


def write_manifest(records: list[VideoRecord], raw_data: Path) -> Path:
    output_path = manifest_path(raw_data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    return output_path


def read_manifest(raw_data: Path) -> list[VideoRecord]:
    path = manifest_path(raw_data)
    if not path.exists():
        return []

    records: list[VideoRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(VideoRecord(**json.loads(line)))
    return records
