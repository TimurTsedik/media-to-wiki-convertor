from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path


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


def iter_video_files(source: Path, extensions: tuple[str, ...], max_depth: int) -> list[Path]:
    if not source.exists():
        return []

    source_depth = len(source.parts)
    matches: list[Path] = []
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        if len(path.parts) - source_depth > max_depth:
            continue
        if path.suffix.lower() in extensions:
            matches.append(path)
    return sorted(matches, key=lambda item: str(item).casefold())


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
