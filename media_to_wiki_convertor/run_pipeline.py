from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from media_to_wiki_convertor.config import PipelineConfig


STAGE_NAMES = [
    "discover",
    "extract-audio",
    "validate-audio",
    "transcribe",
    "chunk-transcripts",
    "extract-knowledge",
    "build-topic-index",
    "build-article-plan",
    "build-catalog",
    "build-course-plan",
    "draft-articles",
    "build-vault",
]


@dataclass(frozen=True)
class PipelineStage:
    name: str
    run: Callable[[PipelineConfig], int]
    expensive: bool = False


def select_stages(from_stage: str | None = None, to_stage: str | None = None) -> list[str]:
    start = stage_index(from_stage) if from_stage else 0
    end = stage_index(to_stage) + 1 if to_stage else len(STAGE_NAMES)
    if start >= end:
        raise ValueError("--from must come before or equal --to")
    return STAGE_NAMES[start:end]


def stage_index(stage: str) -> int:
    if stage not in STAGE_NAMES:
        raise ValueError(f"Unknown stage: {stage}. Known stages: {', '.join(STAGE_NAMES)}")
    return STAGE_NAMES.index(stage)


def run_selected_stages(
    config: PipelineConfig,
    stages: dict[str, PipelineStage],
    from_stage: str | None = None,
    to_stage: str | None = None,
    assume_yes: bool = False,
    dry_run: bool = False,
    say: Callable[[str], None] = print,
) -> int:
    selected = select_stages(from_stage=from_stage, to_stage=to_stage)
    if dry_run:
        say("Pipeline dry run:")
        for name in selected:
            say(f"- {name}")
        return 0

    for name in selected:
        stage = stages[name]
        if stage.expensive and not assume_yes:
            say(f"Stage {name} may call paid LLM APIs. Re-run with --yes to continue.")
            return 1
        say(f"Run stage: {name}")
        code = stage.run(config)
        if code:
            say(f"Stage failed: {name}")
            return code
    say("Pipeline complete.")
    return 0
