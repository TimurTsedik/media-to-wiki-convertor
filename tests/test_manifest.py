from pathlib import Path

from larchenko_kb.manifest import (
    VideoRecord,
    iter_video_files,
    read_manifest,
    stable_video_id,
    write_manifest,
)


def test_iter_video_files_filters_extensions_and_depth(tmp_path: Path) -> None:
    (tmp_path / "lesson.mp4").write_text("video", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("notes", encoding="utf-8")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    (nested / "deep.mov").write_text("video", encoding="utf-8")

    matches = iter_video_files(tmp_path, (".mp4", ".mov"), max_depth=1)

    assert matches == [tmp_path / "lesson.mp4"]


def test_write_and_read_manifest_roundtrip(tmp_path: Path) -> None:
    record = VideoRecord(
        video_id="abc123",
        path="/videos/lesson.mp4",
        title="lesson",
        extension=".mp4",
        size_bytes=42,
        modified_at="2026-06-30T00:00:00+00:00",
    )

    write_manifest([record], tmp_path)

    assert read_manifest(tmp_path) == [record]


def test_stable_video_id_is_repeatable() -> None:
    path = Path("/Volumes/My Passport/ЛАРЧЕНКО/lesson.mp4")

    assert stable_video_id(path) == stable_video_id(path)
