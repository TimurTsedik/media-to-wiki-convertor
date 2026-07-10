from media_to_wiki_convertor.run_pipeline import STAGE_NAMES, select_stages


def test_select_stages_returns_full_pipeline_by_default() -> None:
    assert select_stages() == STAGE_NAMES


def test_default_pipeline_builds_catalog_before_drafting() -> None:
    assert STAGE_NAMES.index("build-article-plan") < STAGE_NAMES.index("build-catalog")
    assert STAGE_NAMES.index("build-catalog") < STAGE_NAMES.index("draft-articles")


def test_default_pipeline_builds_course_plan_before_drafting() -> None:
    assert STAGE_NAMES.index("build-catalog") < STAGE_NAMES.index("build-course-plan")
    assert STAGE_NAMES.index("build-course-plan") < STAGE_NAMES.index("draft-articles")


def test_select_stages_can_start_from_stage() -> None:
    assert select_stages(from_stage="transcribe") == STAGE_NAMES[STAGE_NAMES.index("transcribe") :]


def test_select_stages_can_stop_at_stage() -> None:
    assert select_stages(to_stage="chunk-transcripts") == STAGE_NAMES[
        : STAGE_NAMES.index("chunk-transcripts") + 1
    ]


def test_select_stages_rejects_unknown_stage() -> None:
    try:
        select_stages(from_stage="unknown")
    except ValueError as exc:
        assert "Unknown stage" in str(exc)
    else:
        raise AssertionError("unknown stage was accepted")
