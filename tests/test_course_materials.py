import json
from pathlib import Path

from media_to_wiki_convertor.course_materials import (
    build_course_material_prompt,
    count_course_materials,
    draft_course_material,
    draft_output_path,
    select_course_source_packs,
)


def sample_course_source_pack() -> dict:
    return {
        "chapter": {
            "key": "architecture",
            "title": "Architecture",
            "article_count": 1,
            "topic_count": 1,
            "source_count": 3,
        },
        "articles": [
            {
                "title": "Clean Architecture",
                "slug": "clean-architecture",
                "source_count": 2,
                "count": 4,
            }
        ],
        "topics": [
            {
                "title": "API gateway",
                "source_count": 1,
                "count": 1,
                "sources": [
                    {
                        "video_id": "video-a",
                        "chunk_id": "0001",
                        "start": "00:00:00",
                        "end": "00:10:00",
                        "chunk_text": "API gateway стоит на входе в систему.",
                    }
                ],
            }
        ],
    }


def test_build_course_material_prompt_is_source_bound_and_uses_course_shape() -> None:
    prompt = build_course_material_prompt(
        sample_course_source_pack(),
        known_titles=["Clean Architecture", "Message broker"],
        output_language="ru",
    )

    assert "Используй только COURSE_SOURCE_PACK" in prompt
    assert "Справочные материалы по курсу" in prompt
    assert "# Architecture" in prompt
    assert "[[Clean Architecture]]" in prompt
    assert "[[Message broker]]" in prompt
    assert "API gateway" in prompt
    assert "video-a" in prompt


def test_build_course_material_prompt_compacts_large_source_packs() -> None:
    source_pack = sample_course_source_pack()
    source_pack["topics"] = [
        {
            "title": "First topic",
            "source_count": 1,
            "count": 1,
            "sources": [{"video_id": "a", "chunk_id": "1", "chunk_text": "x" * 200}],
        },
        {
            "title": "Second topic",
            "source_count": 1,
            "count": 1,
            "sources": [{"video_id": "b", "chunk_id": "2", "chunk_text": "y" * 200}],
        },
    ]

    prompt = build_course_material_prompt(
        source_pack,
        known_titles=[],
        max_topics=1,
        max_chunk_chars=20,
    )

    assert "First topic" in prompt
    assert "Second topic" not in prompt
    assert "xxxxxxxxxxxxxxxxxxxx..." in prompt


def test_select_course_source_packs_follows_chapter_order_and_limit(tmp_path: Path) -> None:
    source_packs_dir = tmp_path / "course_plan" / "source_packs"
    source_packs_dir.mkdir(parents=True)
    for key in ["b", "a"]:
        (source_packs_dir / f"{key}.json").write_text(
            json.dumps({"chapter": {"key": key}}),
            encoding="utf-8",
        )
    chapters = [{"key": "b", "title": "B"}, {"key": "a", "title": "A"}]

    selected = select_course_source_packs(tmp_path, chapters, limit=1)

    assert [pack["chapter"]["key"] for pack in selected] == ["b"]


def test_draft_output_path_uses_chapter_key(tmp_path: Path) -> None:
    assert draft_output_path(tmp_path, "architecture") == tmp_path / "course_materials" / "architecture.md"


def test_draft_course_material_writes_markdown_and_skips_existing(tmp_path: Path) -> None:
    calls = 0

    class FakeClient:
        def draft(self, source_pack: dict, known_titles: list[str]) -> str:
            nonlocal calls
            calls += 1
            assert source_pack["chapter"]["title"] == "Architecture"
            assert known_titles == ["Clean Architecture"]
            return "# Architecture\n\nТекст.\n"

    result = draft_course_material(
        tmp_path,
        sample_course_source_pack(),
        FakeClient(),
        known_titles=["Clean Architecture"],
    )
    second = draft_course_material(
        tmp_path,
        sample_course_source_pack(),
        FakeClient(),
        known_titles=["Clean Architecture"],
    )

    assert result.output_path == tmp_path / "course_materials" / "architecture.md"
    assert not result.skipped
    assert second.skipped
    assert calls == 1
    assert count_course_materials(tmp_path) == 1


def test_draft_course_material_force_rebuilds_existing(tmp_path: Path) -> None:
    class FakeClient:
        def draft(self, source_pack: dict, known_titles: list[str]) -> str:
            return "# Architecture\n\nНовый текст.\n"

    output_path = tmp_path / "course_materials" / "architecture.md"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("# Architecture\n\nСтарый текст.\n", encoding="utf-8")

    result = draft_course_material(
        tmp_path,
        sample_course_source_pack(),
        FakeClient(),
        known_titles=["Clean Architecture"],
        force=True,
    )

    assert not result.skipped
    assert output_path.read_text(encoding="utf-8") == "# Architecture\n\nНовый текст.\n"
