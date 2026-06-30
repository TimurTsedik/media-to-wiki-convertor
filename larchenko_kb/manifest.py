from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class VideoRecord:
    video_id: str
    path: str
    title: str
    extension: str
    size_bytes: int
    modified_at: str


def manifest_path(raw_data: Path) -> Path:
    return raw_data / "manifest" / "videos.jsonl"


def stable_video_id(path: Path) -> str:
    return hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]


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

        path = Path(line)
        if not path.is_absolute():
            path = base_dir / path

        if path.suffix.lower() in normalized_extensions:
            paths.append(path)

    return paths


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
