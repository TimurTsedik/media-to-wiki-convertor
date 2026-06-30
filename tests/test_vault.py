import json
from pathlib import Path

from larchenko_kb.vault import build_obsidian_vault, count_vault_articles, note_path_for_title


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


def test_note_path_for_title_splits_slash_titles_into_nested_notes() -> None:
    assert note_path_for_title("Spec Driven Development") == Path("Wiki") / "Spec Driven Development.md"
    assert note_path_for_title("Daily / Standup") == Path("Wiki") / "Daily" / "Standup.md"


def test_build_obsidian_vault_writes_articles_indexes_and_sources(tmp_path: Path) -> None:
    raw_data = tmp_path / "raw data"
    vault = tmp_path / "vault"
    seed_raw_data(raw_data)
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian" / "app.json").write_text("{}", encoding="utf-8")
    (vault / "manual.md").write_text("do not touch", encoding="utf-8")

    result = build_obsidian_vault(raw_data, vault)

    assert result.articles == 2
    assert result.source_notes == 2
    assert count_vault_articles(vault) == 2
    assert (vault / ".obsidian" / "app.json").read_text(encoding="utf-8") == "{}"
    assert (vault / "manual.md").read_text(encoding="utf-8") == "do not touch"

    spec = (vault / "Wiki" / "Spec Driven Development.md").read_text(encoding="utf-8")
    daily = (vault / "Wiki" / "Daily" / "Standup.md").read_text(encoding="utf-8")

    assert "aliases:" in spec
    assert "[[Wiki/Daily/Standup|Daily / Standup]]" in spec
    assert "[[Unknown Topic]]" not in spec
    assert "Unknown Topic" in spec
    assert "[[Wiki/Spec Driven Development|SDD]]" in daily
    assert (vault / "00 Home.md").exists()
    assert (vault / "Index" / "Articles.md").exists()
    assert (vault / "Index" / "Domains.md").exists()
    assert (vault / "Index" / "Sources.md").exists()
    assert (vault / "Index" / "Deferred Topics.md").exists()
    assert "Unknown Topic" in (vault / "Index" / "Unlinked Mentions.md").read_text(encoding="utf-8")
    assert (vault / "Sources" / "Chunks" / "video-a" / "0001.md").exists()
