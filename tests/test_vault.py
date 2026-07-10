import json
from pathlib import Path

from media_to_wiki_convertor.vault import (
    ARTICLE_ROOT,
    build_obsidian_vault,
    count_vault_articles,
    COURSE_ROOT,
    file_link,
    INDEX_ROOT,
    note_path_for_title,
    MANAGED_DIRS,
    rewrite_course_material_map_links,
    rewrite_course_material_links,
    SOURCE_ROOT,
    START_HERE_NOTE,
    SYSTEM_ROOT,
    TRANSCRIPT_ROOT,
)


ARTICLE_PREFIX = f"{ARTICLE_ROOT}/"
COURSE_PREFIX = f"{COURSE_ROOT}/"
INDEX_PREFIX = f"{INDEX_ROOT}/"
SOURCE_PREFIX = f"{SOURCE_ROOT}/"
TRANSCRIPT_PREFIX = f"{TRANSCRIPT_ROOT}/"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def sample_pages() -> list[dict]:
    return [
        {
            "slug": "spec-driven-development",
            "title": "Spec Driven Development",
            "aliases": ["SDD"],
            "tier": "core",
            "domains": ["Software Engineering"],
            "source_count": 2,
            "sources": [
                {"video_id": "video-a", "chunk_id": "0001", "start": "00:00:00", "end": "00:10:00"}
            ],
        },
        {
            "slug": "daily-standup",
            "title": "Daily / Standup",
            "aliases": ["Daily standup"],
            "tier": "supporting",
            "domains": ["Scrum"],
            "source_count": 1,
            "sources": [
                {"video_id": "video-b", "chunk_id": "0002", "start": "00:10:00", "end": "00:20:00"}
            ],
        },
    ]


def seed_raw_data(raw_data: Path) -> None:
    pages = sample_pages()
    write_json(raw_data / "article_plan" / "pages.json", pages)
    write_json(
        raw_data / "article_plan" / "summary.json",
        {"topic_pages": 10, "article_pages": 2, "deferred_pages": 8},
    )
    write_json(
        raw_data / "article_plan" / "deferred.json",
        [{"title": "Deferred Topic", "domains": ["Software Engineering"], "source_count": 1}],
    )
    write_json(
        raw_data / "catalog" / "categories.json",
        [
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
        ],
    )
    write_json(
        raw_data / "catalog" / "summary.json",
        {"categories": 1, "articles": 2, "deferred_topics": 1, "merge_suggestions": 0},
    )
    write_json(
        raw_data / "course_plan" / "chapters.json",
        [
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
                        "sources": [{"video_id": "video-c", "chunk_id": "0003"}],
                    }
                ],
            }
        ],
    )
    (raw_data / "course_materials").mkdir(parents=True)
    (raw_data / "course_materials" / "software-engineering.md").write_text(
        "# Software Engineering\n\nLLM draft.\n\n[[Wiki/Spec Driven Development|Spec Driven Development]]\n",
        encoding="utf-8",
    )
    (raw_data / "draft_articles").mkdir(parents=True)
    (raw_data / "draft_articles" / "spec-driven-development.md").write_text(
        "# Spec Driven Development\n\nСм. [[Daily / Standup]] и [[Unknown Topic]].\n\n## Источники\n- video-a/0001 00:00:00-00:10:00\n",
        encoding="utf-8",
    )
    (raw_data / "draft_articles" / "daily-standup.md").write_text(
        "# Daily / Standup\n\nСвязано с [[Spec Driven Development|SDD]].\n\n## Источники\n- video-b/0002 00:10:00-00:20:00\n",
        encoding="utf-8",
    )
    write_json(
        raw_data / "chunks" / "video-a" / "0001.json",
        {"text": "Текст чанка про SDD.", "start_hms": "00:00:00", "end_hms": "00:10:00"},
    )
    write_json(
        raw_data / "chunks" / "video-b" / "0002.json",
        {"text": "Текст чанка про daily.", "start_hms": "00:10:00", "end_hms": "00:20:00"},
    )
    write_json(
        raw_data / "chunks" / "video-c" / "0003.json",
        {"text": "Текст deferred-темы.", "start_hms": "00:20:00", "end_hms": "00:30:00"},
    )
    (raw_data / "manifest").mkdir(parents=True)
    (raw_data / "manifest" / "videos.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "video_id": "video-a",
                        "path": "/videos/video-a.mp4",
                        "title": "Video A",
                        "extension": ".mp4",
                        "size_bytes": 123,
                        "modified_at": "2026-06-30T00:00:00+00:00",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "video_id": "video-b",
                        "path": "/videos/video-b.mp4",
                        "title": "Video B",
                        "extension": ".mp4",
                        "size_bytes": 456,
                        "modified_at": "2026-06-30T00:00:00+00:00",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "video_id": "video-c",
                        "path": "/videos/video-c.mp4",
                        "title": "Video C",
                        "extension": ".mp4",
                        "size_bytes": 789,
                        "modified_at": "2026-06-30T00:00:00+00:00",
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    transcript_dir = raw_data / "transcripts"
    transcript_dir.mkdir(parents=True)
    for suffix in [".txt", ".srt", ".json"]:
        (transcript_dir / f"video-a{suffix}").write_text("transcript a", encoding="utf-8")
    (transcript_dir / "video-b.txt").write_text("transcript b", encoding="utf-8")
    (transcript_dir / "video-c.txt").write_text("transcript c", encoding="utf-8")


def test_course_first_vault_roots_are_numbered_for_obsidian_scanability() -> None:
    assert START_HERE_NOTE == "00 Start Here.md"
    assert COURSE_ROOT == "01 Course Materials"
    assert ARTICLE_ROOT == "02 Reference Wiki"
    assert INDEX_ROOT == "03 Indexes"
    assert SOURCE_ROOT == "04 Sources"
    assert TRANSCRIPT_ROOT == "05 Transcripts"
    assert SYSTEM_ROOT == "99 System"
    assert MANAGED_DIRS == (
        COURSE_ROOT,
        ARTICLE_ROOT,
        INDEX_ROOT,
        SOURCE_ROOT,
        TRANSCRIPT_ROOT,
        SYSTEM_ROOT,
    )


def test_note_path_for_title_splits_slash_titles_into_nested_notes() -> None:
    assert note_path_for_title("Spec Driven Development") == (
        Path("02 Reference Wiki") / "Spec Driven Development.md"
    )
    assert note_path_for_title("Daily / Standup") == (
        Path("02 Reference Wiki") / "Daily" / "Standup.md"
    )


def test_file_link_escapes_square_brackets_in_label() -> None:
    link = file_link(Path("/tmp/video.mp4"), "[Dmc-1] Recording")

    assert link.startswith(r"[\[Dmc-1\] Recording](file://")


def test_rewrite_course_material_links_rewrites_llm_source_refs_to_chunk_links() -> None:
    markdown = (
        "# AWS\n\n"
        "Источники: [f323d805b520:0011], source:307869628eba#0004, "
        "14c6fbca1e96#0002, overqualified#0001, `video_id:18797da45247#0005`, "
        "video:903e979351ee#0004, course-source-pack:7d1f2472d5ed#0007, "
        "[18797da45247#0002], [missingvideo:0001], source:missingvideo#0002.\n"
        "Markdown: [chunk 0002](source://8dac023c7ead#0002), "
        "[3eef9508e333#0003](https://source/3eef9508e333#0003), "
        "[dc51bf126b22/0008](https://example.com/dc51bf126b22#0008), "
        "[video_903e979351ee#0003](video_903e979351ee#0003), "
        "[chunk 0010](source://video/9eb1cccd1e24#t=01:11:56-01:22:04).\n"
        "Chunk words: video_id:9e4e5e61cab0#chunk:0011 and video:9e4e5e61cab0#chunk-0004.\n"
        "Backtick wrappers: [`8dac023c7ead#0005`] and [`492d35edaba6#0007`](#).\n"
        "См. [[AWS Bedrock]] и [[Sources/Chunks/f323d805b520/0011|готовая ссылка]] "
        "и [[Sources/Chunks/8dac023c7ead/0002|8dac023c7ead/0002]].\n"
    )

    rewritten = rewrite_course_material_links(
        markdown,
        {"AWS Bedrock": f"{ARTICLE_PREFIX}AWS Bedrock"},
        source_targets={("f323d805b520", "0011"), ("307869628eba", "0004")},
        source_alias_targets={
            ("14c6fbca1e96", "0002"): ("14c6fbca1e96", "0002"),
            ("overqualified", "0001"): ("14c6fbca1e96", "0003"),
            ("18797da45247", "0005"): ("18797da45247", "0005"),
            ("18797da45247", "0002"): ("18797da45247", "0002"),
            ("903e979351ee", "0004"): ("903e979351ee", "0004"),
            ("7d1f2472d5ed", "0007"): ("7d1f2472d5ed", "0007"),
            ("8dac023c7ead", "0002"): ("8dac023c7ead", "0002"),
            ("3eef9508e333", "0003"): ("3eef9508e333", "0003"),
            ("dc51bf126b22", "0008"): ("dc51bf126b22", "0008"),
            ("903e979351ee", "0003"): ("903e979351ee", "0003"),
            ("9eb1cccd1e24", "0010"): ("9eb1cccd1e24", "0010"),
            ("9e4e5e61cab0", "0011"): ("9e4e5e61cab0", "0011"),
            ("9e4e5e61cab0", "0004"): ("9e4e5e61cab0", "0004"),
            ("8dac023c7ead", "0005"): ("8dac023c7ead", "0005"),
            ("492d35edaba6", "0007"): ("492d35edaba6", "0007"),
        },
    )

    assert f"[[{SOURCE_PREFIX}Chunks/f323d805b520/0011|f323d805b520/0011]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/307869628eba/0004|307869628eba/0004]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/14c6fbca1e96/0002|14c6fbca1e96/0002]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/14c6fbca1e96/0003|14c6fbca1e96/0003]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/18797da45247/0005|18797da45247/0005]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/18797da45247/0002|18797da45247/0002]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/903e979351ee/0004|903e979351ee/0004]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/7d1f2472d5ed/0007|7d1f2472d5ed/0007]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/8dac023c7ead/0002|8dac023c7ead/0002]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/3eef9508e333/0003|3eef9508e333/0003]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/dc51bf126b22/0008|dc51bf126b22/0008]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/9eb1cccd1e24/0010|9eb1cccd1e24/0010]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/9e4e5e61cab0/0011|9e4e5e61cab0/0011]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/9e4e5e61cab0/0004|9e4e5e61cab0/0004]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/8dac023c7ead/0005|8dac023c7ead/0005]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/492d35edaba6/0007|492d35edaba6/0007]]" in rewritten
    assert f"[[[{SOURCE_ROOT}/" not in rewritten
    assert f"`[[{SOURCE_ROOT}/" not in rewritten
    assert "](https://source/" not in rewritten
    assert "](source://" not in rewritten
    assert "[missingvideo:0001]" in rewritten
    assert "source:missingvideo#0002" in rewritten
    assert f"[[{ARTICLE_PREFIX}AWS Bedrock|AWS Bedrock]]" in rewritten
    assert f"[[{SOURCE_PREFIX}Chunks/f323d805b520/0011|готовая ссылка]]" in rewritten


def test_rewrite_course_material_map_links_links_articles_and_local_headings() -> None:
    markdown = """# Software Engineering

## Карта раздела
- [[Spec Driven Development]]
- Deferred Topic
- Missing Topic

## Подтемы курса

### Deferred Topic
Текст.

### CI/CD и monorepository
Текст.

## Полный список подтем и источников

- Missing Topic
"""

    rewritten = rewrite_course_material_map_links(
        markdown,
        chapter_key="software-engineering",
        link_targets={"Spec Driven Development": f"{ARTICLE_PREFIX}Spec Driven Development"},
    )

    assert f"- [[{ARTICLE_PREFIX}Spec Driven Development|Spec Driven Development]]" in rewritten
    assert f"- [[{COURSE_PREFIX}software-engineering#Deferred Topic|Deferred Topic]]" in rewritten
    assert (
        f"- [[{COURSE_PREFIX}software-engineering#Полный список подтем и источников|Missing Topic]]"
        in rewritten
    )


def test_rewrite_course_material_map_links_fuzzy_matches_heading_titles() -> None:
    markdown = """# DevOps

## Карта раздела
- CI/CD

## Подтемы курса

### CI/CD и monorepository
Текст.
"""

    rewritten = rewrite_course_material_map_links(
        markdown,
        chapter_key="devops",
        link_targets={},
    )

    assert f"- [[{COURSE_PREFIX}devops#CI/CD и monorepository|CI/CD]]" in rewritten


def test_rewrite_course_material_map_links_handles_english_section_headings() -> None:
    markdown = """# DevOps

## Section Map
- [[Spec Driven Development]]
- CI/CD
- Missing Topic

## Course Topics

### CI/CD and monorepository
Text.

## Full Topic and Source Index

- Missing Topic
"""

    rewritten = rewrite_course_material_map_links(
        markdown,
        chapter_key="devops",
        link_targets={"Spec Driven Development": f"{ARTICLE_PREFIX}Spec Driven Development"},
    )

    assert f"- [[{ARTICLE_PREFIX}Spec Driven Development|Spec Driven Development]]" in rewritten
    assert f"- [[{COURSE_PREFIX}devops#CI/CD and monorepository|CI/CD]]" in rewritten
    assert f"- [[{COURSE_PREFIX}devops#Full Topic and Source Index|Missing Topic]]" in rewritten
    assert "## Section Map" in rewritten


def test_build_obsidian_vault_writes_articles_indexes_and_sources(tmp_path: Path) -> None:
    raw_data = tmp_path / "raw data"
    vault = tmp_path / "vault"
    seed_raw_data(raw_data)
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian" / "app.json").write_text("{}", encoding="utf-8")
    (vault / "manual.md").write_text("do not touch", encoding="utf-8")

    result = build_obsidian_vault(raw_data, vault)

    assert result.articles == 2
    assert result.source_notes == 3
    assert result.transcript_notes == 3
    assert count_vault_articles(vault) == 2
    assert (vault / ".obsidian" / "app.json").read_text(encoding="utf-8") == "{}"
    assert (vault / "manual.md").read_text(encoding="utf-8") == "do not touch"

    spec = (vault / ARTICLE_ROOT / "Spec Driven Development.md").read_text(encoding="utf-8")
    daily = (vault / ARTICLE_ROOT / "Daily" / "Standup.md").read_text(encoding="utf-8")

    assert "aliases:" in spec
    assert f"[[{ARTICLE_PREFIX}Daily/Standup|Daily / Standup]]" in spec
    assert "## Исходные транскрибации" in spec
    assert f"[[{TRANSCRIPT_PREFIX}video-a|Video A]]" in spec
    assert f"[[{SOURCE_PREFIX}Chunks/video-a/0001|video-a/0001]]" in spec
    assert "[[Unknown Topic]]" not in spec
    assert "Unknown Topic" in spec
    assert f"[[{ARTICLE_PREFIX}Spec Driven Development|SDD]]" in daily
    assert (vault / START_HERE_NOTE).exists()
    assert (vault / INDEX_ROOT / "Articles.md").exists()
    assert (vault / INDEX_ROOT / "Domains.md").exists()
    assert (vault / INDEX_ROOT / "Sources.md").exists()
    assert (vault / INDEX_ROOT / "Catalog.md").exists()
    assert (vault / INDEX_ROOT / "Catalog" / "software-engineering.md").exists()
    assert (vault / COURSE_ROOT / "00 Справочные материалы по курсу.md").exists()
    assert (vault / COURSE_ROOT / "software-engineering.md").exists()
    assert (vault / INDEX_ROOT / "Deferred Topics.md").exists()
    assert "Unknown Topic" in (vault / INDEX_ROOT / "Unlinked Mentions.md").read_text(
        encoding="utf-8"
    )
    home = (vault / START_HERE_NOTE).read_text(encoding="utf-8")
    catalog_index = (vault / INDEX_ROOT / "Catalog.md").read_text(encoding="utf-8")
    catalog_category = (vault / INDEX_ROOT / "Catalog" / "software-engineering.md").read_text(
        encoding="utf-8"
    )
    assert f"[[{INDEX_PREFIX}Catalog|Catalog]]" in home
    assert (
        f"[[{COURSE_PREFIX}00 Справочные материалы по курсу|Справочные материалы по курсу]]"
        in home
    )
    assert f"[[{INDEX_PREFIX}Catalog/software-engineering|Software Engineering]]" in catalog_index
    course_index = (
        vault / COURSE_ROOT / "00 Справочные материалы по курсу.md"
    ).read_text(encoding="utf-8")
    course_chapter = (vault / COURSE_ROOT / "software-engineering.md").read_text(
        encoding="utf-8"
    )
    assert f"[[{COURSE_PREFIX}software-engineering|Software Engineering]]" in course_index
    assert "LLM draft." in course_chapter
    assert f"[[{ARTICLE_PREFIX}Spec Driven Development|Spec Driven Development]]" in course_chapter
    assert "## Полный список подтем и источников" in course_chapter
    assert "Deferred Topic" in course_chapter
    assert f"[[{SOURCE_PREFIX}Chunks/video-c/0003|video-c/0003]]" in course_chapter
    assert f"[[{ARTICLE_PREFIX}Spec Driven Development|Spec Driven Development]]" in catalog_category
    assert f"[[{ARTICLE_PREFIX}Deferred Topic" not in catalog_category
    assert "Deferred Topic" in catalog_category
    assert f"[[{SOURCE_PREFIX}Chunks/video-c/0003|video-c/0003]]" in catalog_category
    sources_index = (vault / INDEX_ROOT / "Sources.md").read_text(encoding="utf-8")
    assert f"[[{INDEX_PREFIX}Catalog/software-engineering|Deferred Topic]]" in sources_index
    assert f"[[{ARTICLE_PREFIX}Deferred Topic" not in sources_index
    source_note = (vault / SOURCE_ROOT / "Chunks" / "video-a" / "0001.md").read_text(
        encoding="utf-8"
    )
    assert f"[[{TRANSCRIPT_PREFIX}video-a|Video A]]" in source_note
    deferred_source_note = (
        vault / SOURCE_ROOT / "Chunks" / "video-c" / "0003.md"
    ).read_text(encoding="utf-8")
    assert f"[[{TRANSCRIPT_PREFIX}video-c|Video C]]" in deferred_source_note
    assert f"[[{INDEX_PREFIX}Catalog/software-engineering|Deferred Topic]]" in deferred_source_note

    transcript_index = (vault / f"{TRANSCRIPT_ROOT}.md").read_text(encoding="utf-8")
    transcript_note = (vault / TRANSCRIPT_ROOT / "video-a.md").read_text(encoding="utf-8")
    assert f"[[{TRANSCRIPT_PREFIX}video-a|Video A]]" in transcript_index
    assert "[TXT](" in transcript_note
    assert "[SRT](" in transcript_note
    assert "[JSON](" in transcript_note
    assert f"[[{SOURCE_PREFIX}Chunks/video-a/0001|video-a/0001]]" in transcript_note


def test_build_obsidian_vault_localizes_course_materials_to_english(tmp_path: Path) -> None:
    raw_data = tmp_path / "raw data"
    vault = tmp_path / "vault"
    seed_raw_data(raw_data)
    (raw_data / "course_materials").mkdir(parents=True, exist_ok=True)
    (raw_data / "course_materials" / "software-engineering.md").unlink()

    build_obsidian_vault(raw_data, vault, output_language="en")

    assert (vault / COURSE_ROOT / "00 Course Reference Materials.md").exists()
    course_index = (vault / COURSE_ROOT / "00 Course Reference Materials.md").read_text(
        encoding="utf-8"
    )
    course_chapter = (vault / COURSE_ROOT / "software-engineering.md").read_text(
        encoding="utf-8"
    )
    home = (vault / START_HERE_NOTE).read_text(encoding="utf-8")

    assert "# Course Reference Materials" in course_index
    assert f"[[{COURSE_PREFIX}00 Course Reference Materials|Course Reference Materials]]" in home
    assert "## Section Map" in course_chapter
    assert "## Course Topics" in course_chapter
    assert "No standalone wiki articles yet." not in course_chapter
    assert "## Карта раздела" not in course_chapter
    assert "## Подтемы курса" not in course_chapter
    assert "# Media To Wiki Vault" in home
    assert "## Navigation" in home
    assert "## Vault Status" in home
    assert "Larchenko" not in home

    article = (vault / ARTICLE_ROOT / "Spec Driven Development.md").read_text(encoding="utf-8")
    assert "## Source Transcripts" in article
    assert "## Исходные транскрибации" not in article


def test_build_obsidian_vault_localizes_existing_draft_headings_to_english(tmp_path: Path) -> None:
    raw_data = tmp_path / "raw data"
    vault = tmp_path / "vault"
    seed_raw_data(raw_data)
    (raw_data / "course_materials" / "software-engineering.md").write_text(
        """# Software Engineering

## Коротко
LLM draft.

## Карта раздела
- [[Spec Driven Development]]
- Deferred Topic

## Подтемы курса

### Deferred Topic
Text.
""",
        encoding="utf-8",
    )

    build_obsidian_vault(raw_data, vault, output_language="en")

    article = (vault / ARTICLE_ROOT / "Spec Driven Development.md").read_text(encoding="utf-8")
    course_chapter = (vault / COURSE_ROOT / "software-engineering.md").read_text(
        encoding="utf-8"
    )

    assert "## Sources" in article
    assert "## Источники" not in article
    assert "## Quick Summary" in course_chapter
    assert "## Section Map" in course_chapter
    assert "## Course Topics" in course_chapter
    assert "## Full Topic and Source Index" in course_chapter
    assert "## Коротко" not in course_chapter
    assert "## Карта раздела" not in course_chapter
    assert "## Подтемы курса" not in course_chapter


def test_build_obsidian_vault_omits_catalog_link_when_catalog_is_missing(tmp_path: Path) -> None:
    raw_data = tmp_path / "raw data"
    vault = tmp_path / "vault"
    seed_raw_data(raw_data)
    catalog_dir = raw_data / "catalog"
    for path in catalog_dir.glob("*.json"):
        path.unlink()

    build_obsidian_vault(raw_data, vault)

    home = (vault / START_HERE_NOTE).read_text(encoding="utf-8")
    assert f"[[{INDEX_PREFIX}Catalog|Catalog]]" not in home
    assert not (vault / INDEX_ROOT / "Catalog.md").exists()
