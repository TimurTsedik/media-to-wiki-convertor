import json
from pathlib import Path

from media_to_wiki_convertor.catalog import build_catalog, count_catalog_categories, write_catalog


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_build_catalog_groups_articles_and_deferred_topics_by_domain() -> None:
    pages = [
        {
            "title": "Pull Request Review Skill",
            "slug": "pull-request-review-skill",
            "domains": ["software engineering"],
            "source_count": 3,
            "count": 5,
        }
    ]
    deferred = [
        {
            "title": "AI code review",
            "domains": ["Software Engineering"],
            "source_count": 1,
            "count": 2,
        }
    ]

    catalog = build_catalog(pages, deferred)

    category = catalog["categories"][0]
    assert category["key"] == "software-engineering"
    assert category["title"] == "Software Engineering"
    assert category["article_count"] == 1
    assert category["deferred_count"] == 1
    assert category["source_count"] == 4
    assert category["articles"] == [
        {
            "title": "Pull Request Review Skill",
            "slug": "pull-request-review-skill",
            "source_count": 3,
            "count": 5,
        }
    ]
    assert category["topics"] == [{"title": "AI code review", "source_count": 1, "count": 2}]


def test_build_catalog_preserves_common_domain_acronyms() -> None:
    catalog = build_catalog(
        [
            {
                "title": "AWS Lambda",
                "slug": "aws-lambda",
                "domains": ["AI / LLM / AWS"],
                "source_count": 1,
                "count": 1,
            }
        ],
        [],
    )

    assert catalog["categories"][0]["title"] == "AI LLM AWS"


def test_build_catalog_uses_suggested_section_then_uncategorized() -> None:
    catalog = build_catalog(
        [
            {
                "title": "Facilitation Patterns",
                "slug": "facilitation-patterns",
                "suggested_sections": ["Team Practice"],
                "source_count": 1,
                "count": 1,
            }
        ],
        [{"title": "Loose Topic", "source_count": 1, "count": 1}],
    )

    assert [category["title"] for category in catalog["categories"]] == [
        "Team Practice",
        "Uncategorized",
    ]


def test_build_catalog_suggests_alias_for_exact_title_match() -> None:
    catalog = build_catalog(
        [
            {
                "title": "AI Code Review",
                "slug": "ai-code-review",
                "domains": ["Architecture"],
                "source_count": 2,
                "count": 4,
            }
        ],
        [{"title": "AI code review", "domains": ["architecture"], "source_count": 1, "count": 1}],
    )

    assert catalog["merge_suggestions"] == [
        {
            "topic_title": "AI code review",
            "topic_category": "Architecture",
            "article_title": "AI Code Review",
            "article_slug": "ai-code-review",
            "action": "merge_as_alias",
            "score": 1.0,
            "reason": "normalized title match",
        }
    ]
    assert catalog["orphan_topics"] == []


def test_build_catalog_suggests_section_for_meaningful_same_category_overlap() -> None:
    catalog = build_catalog(
        [
            {
                "title": "Pull Request Review Skill",
                "slug": "pull-request-review-skill",
                "domains": ["Software Engineering"],
                "source_count": 4,
                "count": 6,
            }
        ],
        [
            {
                "title": "Pull request review workflow",
                "domains": ["Software Engineering"],
                "source_count": 1,
                "count": 1,
            }
        ],
    )

    assert catalog["merge_suggestions"][0]["action"] == "merge_as_section"
    assert catalog["merge_suggestions"][0]["article_title"] == "Pull Request Review Skill"
    assert catalog["orphan_topics"] == []


def test_build_catalog_does_not_suggest_merge_for_single_weak_overlap() -> None:
    catalog = build_catalog(
        [
            {
                "title": "Pull Request Review Skill",
                "slug": "pull-request-review-skill",
                "domains": ["Software Engineering"],
                "source_count": 4,
                "count": 6,
            }
        ],
        [{"title": "AI code review", "domains": ["Software Engineering"], "source_count": 1, "count": 1}],
    )

    assert catalog["merge_suggestions"][0]["action"] == "catalog_only"
    assert catalog["merge_suggestions"][0]["article_title"] == ""
    assert catalog["orphan_topics"] == [
        {"title": "AI code review", "source_count": 1, "count": 1, "category": "Software Engineering"}
    ]


def test_write_catalog_writes_expected_files_and_count(tmp_path: Path) -> None:
    raw_data = tmp_path / "raw-data"
    write_json(
        raw_data / "article_plan" / "pages.json",
        [{"title": "Architecture", "slug": "architecture", "domains": ["Architecture"]}],
    )
    write_json(
        raw_data / "article_plan" / "deferred.json",
        [{"title": "Orphan Topic", "domains": ["Delivery"]}],
    )

    catalog = build_catalog(
        json.loads((raw_data / "article_plan" / "pages.json").read_text(encoding="utf-8")),
        json.loads((raw_data / "article_plan" / "deferred.json").read_text(encoding="utf-8")),
    )
    output_dir = write_catalog(raw_data, catalog)

    assert output_dir == raw_data / "catalog"
    assert count_catalog_categories(raw_data) == 2
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "categories.json").exists()
    assert (output_dir / "merge_suggestions.json").exists()
    assert (output_dir / "orphan_topics.json").exists()
