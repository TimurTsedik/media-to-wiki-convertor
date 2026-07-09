from pathlib import Path

from media_to_wiki_convertor.manifest import (
    VideoRecord,
    iter_video_files,
    read_video_path_list,
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


def test_iter_video_files_reports_directory_progress(tmp_path: Path) -> None:
    nested = tmp_path / "course"
    nested.mkdir()
    (nested / "lesson.mov").write_text("video", encoding="utf-8")
    visited: list[Path] = []

    matches = iter_video_files(
        tmp_path,
        (".mov",),
        max_depth=2,
        on_progress=visited.append,
    )

    assert matches == [nested / "lesson.mov"]
    assert tmp_path in visited
    assert nested in visited


def test_read_video_path_list_supports_relative_and_absolute_paths(tmp_path: Path) -> None:
    base = tmp_path / "videos"
    base.mkdir()
    relative_video = base / "lesson 1.mp4"
    absolute_video = tmp_path / "external.mov"
    ignored_file = base / "notes.txt"
    relative_video.write_text("video", encoding="utf-8")
    absolute_video.write_text("video", encoding="utf-8")
    ignored_file.write_text("notes", encoding="utf-8")
    list_path = tmp_path / "video-list.txt"
    list_path.write_text(
        "\n".join(
            [
                "# comments are ignored",
                "lesson 1.mp4",
                str(absolute_video),
                "notes.txt",
                "",
            ]
        ),
        encoding="utf-8",
    )

    paths = read_video_path_list(list_path, base, (".mp4", ".mov"))

    assert paths == [relative_video, absolute_video]


def test_read_video_path_list_strips_leading_icon_when_needed(tmp_path: Path) -> None:
    base = tmp_path / "videos"
    base.mkdir()
    video = base / "lesson.mp4"
    video.write_text("video", encoding="utf-8")
    list_path = tmp_path / "video-list.txt"
    list_path.write_text("\uf008 lesson.mp4\n", encoding="utf-8")

    paths = read_video_path_list(list_path, base, (".mp4",))

    assert paths == [video]


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
