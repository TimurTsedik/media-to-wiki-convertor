import json
from pathlib import Path

from media_to_wiki_convertor.course_plan import (
    build_course_plan,
    count_course_plan_chapters,
    write_course_plan,
)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_build_course_plan_promotes_catalog_categories_to_course_chapters() -> None:
    catalog_categories = [
        {
            "key": "software-engineering",
            "title": "Software Engineering",
            "article_count": 1,
            "deferred_count": 1,
            "source_count": 3,
            "articles": [
                {
                    "title": "Spec Driven Development",
                    "slug": "spec-driven-development",
                    "source_count": 2,
                    "count": 4,
                }
            ],
            "topics": [
                {
                    "title": "Deferred Topic",
                    "source_count": 1,
                    "count": 1,
                    "sources": [
                        {
                            "video_id": "video-c",
                            "chunk_id": "0003",
                            "start": "00:20:00",
                            "end": "00:30:00",
                        }
                    ],
                }
            ],
        }
    ]

    plan = build_course_plan(catalog_categories)

    assert plan["summary"] == {
        "chapters": 1,
        "articles": 1,
        "topics": 1,
        "sources": 3,
    }
    assert plan["chapters"] == [
        {
            "key": "software-engineering",
            "title": "Software Engineering",
            "article_count": 1,
            "topic_count": 1,
            "source_count": 3,
            "articles": [
                {
                    "title": "Spec Driven Development",
                    "slug": "spec-driven-development",
                    "source_count": 2,
                    "count": 4,
                }
            ],
            "topics": [
                {
                    "title": "Deferred Topic",
                    "source_count": 1,
                    "count": 1,
                    "sources": [
                        {
                            "video_id": "video-c",
                            "chunk_id": "0003",
                            "start": "00:20:00",
                            "end": "00:30:00",
                        }
                    ],
                }
            ],
        }
    ]


def test_write_course_plan_writes_chapters_summary_and_source_packs(tmp_path: Path) -> None:
    raw_data = tmp_path / "raw-data"
    write_json(
        raw_data / "chunks" / "video-c" / "0003.json",
        {"text": "Текст deferred-темы.", "start_hms": "00:20:00", "end_hms": "00:30:00"},
    )
    plan = build_course_plan(
        [
            {
                "key": "software-engineering",
                "title": "Software Engineering",
                "source_count": 1,
                "articles": [],
                "topics": [
                    {
                        "title": "Deferred Topic",
                        "source_count": 1,
                        "count": 1,
                        "sources": [{"video_id": "video-c", "chunk_id": "0003"}],
                    }
                ],
            }
        ]
    )

    output_dir = write_course_plan(raw_data, plan)

    assert output_dir == raw_data / "course_plan"
    assert count_course_plan_chapters(raw_data) == 1
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "chapters.json").exists()
    source_pack = json.loads(
        (output_dir / "source_packs" / "software-engineering.json").read_text(encoding="utf-8")
    )
    assert source_pack["chapter"]["title"] == "Software Engineering"
    assert source_pack["topics"][0]["sources"][0]["chunk_text"] == "Текст deferred-темы."
