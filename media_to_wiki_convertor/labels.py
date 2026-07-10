from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WikiLabels:
    article_summary: str
    article_why: str
    article_core_ideas: str
    article_practices: str
    article_mistakes: str
    article_related: str
    sources: str
    course_materials_title: str
    course_summary: str
    course_section_map: str
    course_topics: str
    course_related: str
    full_topic_source_index: str
    no_course_articles: str
    no_course_topics: str


RU_LABELS = WikiLabels(
    article_summary="Коротко",
    article_why="Зачем это важно",
    article_core_ideas="Основные идеи",
    article_practices="Практики",
    article_mistakes="Типичные ошибки",
    article_related="Связанные темы",
    sources="Источники",
    course_materials_title="Справочные материалы по курсу",
    course_summary="Коротко",
    course_section_map="Карта раздела",
    course_topics="Подтемы курса",
    course_related="Связанные материалы",
    full_topic_source_index="Полный список подтем и источников",
    no_course_articles="Пока нет отдельных wiki-статей.",
    no_course_topics="Пока нет подтем из расширенного списка.",
)


EN_LABELS = WikiLabels(
    article_summary="Quick Summary",
    article_why="Why It Matters",
    article_core_ideas="Core Ideas",
    article_practices="Practices",
    article_mistakes="Common Mistakes",
    article_related="Related Topics",
    sources="Sources",
    course_materials_title="Course Reference Materials",
    course_summary="Quick Summary",
    course_section_map="Section Map",
    course_topics="Course Topics",
    course_related="Related Materials",
    full_topic_source_index="Full Topic and Source Index",
    no_course_articles="No standalone wiki articles yet.",
    no_course_topics="No extended-list topics yet.",
)


def language_code(language: str) -> str:
    return (language or "ru").strip().casefold().replace("_", "-").split("-", 1)[0]


def wiki_labels(language: str = "ru") -> WikiLabels:
    if language_code(language) == "en":
        return EN_LABELS
    return RU_LABELS


def label_aliases(field_name: str, output_language: str = "ru") -> list[str]:
    preferred = getattr(wiki_labels(output_language), field_name)
    aliases = [preferred, getattr(RU_LABELS, field_name), getattr(EN_LABELS, field_name)]
    return list(dict.fromkeys(aliases))


def heading_translation_map(output_language: str = "ru") -> dict[str, str]:
    target = wiki_labels(output_language)
    source = RU_LABELS if target is EN_LABELS else EN_LABELS
    fields = (
        "article_summary",
        "article_why",
        "article_core_ideas",
        "article_practices",
        "article_mistakes",
        "article_related",
        "sources",
        "course_summary",
        "course_section_map",
        "course_topics",
        "course_related",
        "full_topic_source_index",
    )
    return {getattr(source, field): getattr(target, field) for field in fields}
