from __future__ import annotations

import argparse
from pathlib import Path
import time

from media_to_wiki_convertor.article_plan import (
    build_article_plan as build_article_plan_payload,
    count_article_plan_pages,
    read_topic_pages,
    write_article_plan,
)
from media_to_wiki_convertor.audio import audio_is_valid, count_existing_audio, extract_audio_for_record, has_ffmpeg
from media_to_wiki_convertor.chunks import chunk_transcript_record, count_existing_chunks
from media_to_wiki_convertor.config import PipelineConfig, load_config
from media_to_wiki_convertor.draft_articles import (
    OpenAIArticleClient,
    build_article_prompt,
    count_draft_articles,
    draft_article,
    read_article_pages,
    select_source_packs,
)
from media_to_wiki_convertor.knowledge import (
    OpenAIKnowledgeClient,
    build_extraction_prompt,
    chunk_payloads,
    count_existing_knowledge,
    extract_chunk_knowledge,
    select_chunk_payloads,
)
from media_to_wiki_convertor.manifest import (
    build_video_record,
    iter_video_files,
    manifest_path,
    read_video_path_list,
    read_manifest,
    write_manifest,
)
from media_to_wiki_convertor.project import ProjectSettings, init_project, update_project_config
from media_to_wiki_convertor.run_events import RunEventStatus, RunEventWriter, format_wall_time, utc_now
from media_to_wiki_convertor.run_pipeline import PipelineStage, run_selected_stages
from media_to_wiki_convertor.transcription import (
    append_transcription_log,
    count_existing_transcripts,
    format_elapsed,
    import_transcript as import_transcript_file,
    transcribe_record,
)
from media_to_wiki_convertor.topic_index import (
    build_topic_index as build_topic_index_payload,
    count_topic_index_pages,
    read_knowledge_payloads,
    write_topic_index,
)
from media_to_wiki_convertor.vault import build_obsidian_vault


def say(message: str) -> None:
    print(message, flush=True)


def ensure_raw_layout(raw_data: Path) -> None:
    for relative in [
        "manifest",
        "audio",
        "transcripts",
        "chunks",
        "extracted_knowledge",
        "topic_index",
        "article_plan",
        "draft_articles",
        "summaries/chunks",
        "summaries/videos",
        "logs",
    ]:
        (raw_data / relative).mkdir(parents=True, exist_ok=True)


def print_status(config: PipelineConfig) -> None:
    ensure_raw_layout(config.paths.raw_data)
    records = read_manifest(config.paths.raw_data)

    say("Larchenko KB pipeline")
    say(f"video_source: {config.paths.video_source}")
    say(f"raw_data:     {config.paths.raw_data}")
    say(f"vault:        {config.paths.vault}")
    say(f"manifest:     {manifest_path(config.paths.raw_data)}")
    say(f"videos:       {len(records)}")
    say(f"audio_wav:    {count_existing_audio(config.paths.raw_data)}")
    say(f"transcripts:  {count_existing_transcripts(config.paths.raw_data)}")
    say(f"chunks:       {count_existing_chunks(config.paths.raw_data)}")
    say(f"knowledge:    {count_existing_knowledge(config.paths.raw_data)}")
    say(f"topic_pages:  {count_topic_index_pages(config.paths.raw_data)}")
    say(f"article_pages:{count_article_plan_pages(config.paths.raw_data)}")
    say(f"draft_articles:{count_draft_articles(config.paths.raw_data)}")


def discover(config: PipelineConfig, source_override: Path | None = None) -> int:
    ensure_raw_layout(config.paths.raw_data)
    source = source_override or config.paths.video_source
    scanned_dirs = 0

    def report_progress(path: Path) -> None:
        nonlocal scanned_dirs
        scanned_dirs += 1
        if scanned_dirs == 1 or scanned_dirs % 25 == 0:
            say(f"Scanning directory {scanned_dirs}: {path}")

    videos = iter_video_files(
        source,
        config.discover.video_extensions,
        config.discover.max_depth,
        on_progress=report_progress,
    )
    records = [build_video_record(path) for path in videos]
    output_path = write_manifest(records, config.paths.raw_data)
    say(f"Discovered {len(records)} video file(s).")
    say(f"Wrote manifest: {output_path}")
    return len(records)


def import_video_list(config: PipelineConfig, list_path: Path, base_dir: Path | None = None) -> int:
    ensure_raw_layout(config.paths.raw_data)
    base = base_dir or config.paths.video_source
    videos = read_video_path_list(list_path, base, config.discover.video_extensions)
    records = [build_video_record(path) for path in videos]
    output_path = write_manifest(records, config.paths.raw_data)
    say(f"Imported {len(records)} video file(s).")
    say(f"Wrote manifest: {output_path}")
    return len(records)


def import_transcript(config: PipelineConfig, video_id: str, file_path: Path, force: bool) -> int:
    ensure_raw_layout(config.paths.raw_data)
    records = read_manifest(config.paths.raw_data)
    record = next((item for item in records if item.video_id == video_id), None)
    if record is None:
        say(f"Video id not found in manifest: {video_id}")
        say("Run `python3 -m media_to_wiki_convertor discover` or `import-list` first.")
        return 1

    try:
        result = import_transcript_file(
            record,
            config.paths.raw_data,
            file_path,
            language=config.transcription.language,
            force=force,
        )
    except Exception as exc:
        say(f"Transcript import failed for {video_id}: {exc}")
        return 1

    if result.skipped:
        say(f"Transcript import skipped for {video_id}: {result.paths.json_path}")
    else:
        say(f"Transcript imported for {video_id}: {result.paths.json_path}")
    return 0


def planned_stage(name: str) -> None:
    say(f"{name} is planned, but not implemented yet.")
    say("Run `python3 -m media_to_wiki_convertor discover` first to create the video manifest.")


def start_run_event(writer: RunEventWriter, stage: str, item_id: str, message: str):
    started_at = utc_now()
    writer.write(
        stage=stage,
        item_id=item_id,
        status="started",
        started_at=started_at,
        finished_at=started_at,
        message=message,
    )
    return started_at


def finish_run_event(
    writer: RunEventWriter,
    *,
    stage: str,
    item_id: str,
    status: RunEventStatus,
    started_at,
    message: str,
    error: str | None = None,
):
    finished_at = utc_now()
    writer.write(
        stage=stage,
        item_id=item_id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        message=message,
        error=error,
    )
    return finished_at


def extract_audio(config: PipelineConfig) -> int:
    ensure_raw_layout(config.paths.raw_data)
    records = read_manifest(config.paths.raw_data)
    if not records:
        say("No videos in manifest.")
        say("Run `python3 -m media_to_wiki_convertor discover` first.")
        return 0
    if not has_ffmpeg():
        say("ffmpeg is not installed or is not available on PATH.")
        say("Install it before running audio extraction, for example: `brew install ffmpeg`.")
        return 1

    extracted = 0
    skipped = 0
    failed = 0
    events = RunEventWriter(config.paths.raw_data)
    for index, record in enumerate(records, start=1):
        monotonic_started_at = time.monotonic()
        event_started_at = start_run_event(
            events,
            "extract-audio",
            record.video_id,
            f"audio start {record.video_id}",
        )
        audio_path = config.paths.raw_data / "audio" / f"{record.video_id}.wav"
        say(
            f"[{index}/{len(records)}] audio start {record.video_id} "
            f"at {format_wall_time(event_started_at)}: {audio_path}"
        )
        try:
            result = extract_audio_for_record(record, config.paths.raw_data)
        except Exception as exc:
            failed += 1
            elapsed = format_elapsed(time.monotonic() - monotonic_started_at)
            finished_at = finish_run_event(
                events,
                stage="extract-audio",
                item_id=record.video_id,
                status="failed",
                started_at=event_started_at,
                message=f"audio failed {record.video_id}",
                error=str(exc),
            )
            say(
                f"[{index}/{len(records)}] audio failed {record.video_id} "
                f"at {format_wall_time(finished_at)} in {elapsed}: {exc}"
            )
            continue

        elapsed = format_elapsed(time.monotonic() - monotonic_started_at)
        if result.skipped:
            skipped += 1
            status: RunEventStatus = "skipped"
            message = f"audio skipped {record.video_id}"
        else:
            extracted += 1
            status = "success"
            message = f"audio extracted {record.video_id}"
        finished_at = finish_run_event(
            events,
            stage="extract-audio",
            item_id=record.video_id,
            status=status,
            started_at=event_started_at,
            message=message,
        )
        if result.skipped:
            say(
                f"[{index}/{len(records)}] audio skip {record.video_id} "
                f"at {format_wall_time(finished_at)} in {elapsed}: {result.output_path}"
            )
        else:
            say(
                f"[{index}/{len(records)}] audio extracted {record.video_id} "
                f"at {format_wall_time(finished_at)} in {elapsed}: {result.output_path}"
            )

    say(f"Audio extraction complete: extracted={extracted}, skipped={skipped}, failed={failed}")
    return 1 if failed else 0


def validate_audio(config: PipelineConfig) -> int:
    ensure_raw_layout(config.paths.raw_data)
    records = read_manifest(config.paths.raw_data)
    invalid = 0
    missing = 0

    for index, record in enumerate(records, start=1):
        audio_path = config.paths.raw_data / "audio" / f"{record.video_id}.wav"
        if not audio_path.exists():
            missing += 1
            say(f"[{index}/{len(records)}] missing {record.video_id}: {audio_path}")
            continue
        if audio_is_valid(audio_path):
            say(f"[{index}/{len(records)}] valid {record.video_id}: {audio_path}")
        else:
            invalid += 1
            say(f"[{index}/{len(records)}] invalid {record.video_id}: {audio_path}")

    say(f"Audio validation complete: valid={len(records) - invalid - missing}, invalid={invalid}, missing={missing}")
    return 1 if invalid or missing else 0


def transcribe(config: PipelineConfig) -> int:
    ensure_raw_layout(config.paths.raw_data)
    records = read_manifest(config.paths.raw_data)
    if not records:
        say("No videos in manifest.")
        say("Run `python3 -m media_to_wiki_convertor discover` or `import-list` first.")
        return 0
    if config.transcription.engine != "mlx-whisper":
        say(f"Unsupported transcription engine: {config.transcription.engine}")
        say("Supported engine: mlx-whisper")
        return 1

    created = 0
    skipped = 0
    failed = 0
    events = RunEventWriter(config.paths.raw_data)
    say(
        "Transcription settings: "
        f"engine={config.transcription.engine}, "
        f"model={config.transcription.model}, "
        f"language={config.transcription.language}"
    )
    batch_started_at = time.monotonic()
    for index, record in enumerate(records, start=1):
        item_started_at = time.monotonic()
        event_started_at = start_run_event(
            events,
            "transcribe",
            record.video_id,
            f"transcribe start {record.video_id}",
        )
        audio_path = config.paths.raw_data / "audio" / f"{record.video_id}.wav"
        say(
            f"[{index}/{len(records)}] transcribe start {record.video_id} "
            f"at {format_wall_time(event_started_at)}: {audio_path}"
        )
        try:
            result = transcribe_record(
                record,
                config.paths.raw_data,
                language=config.transcription.language,
                model=config.transcription.model,
            )
        except Exception as exc:
            failed += 1
            elapsed = format_elapsed(time.monotonic() - item_started_at)
            append_transcription_log(config.paths.raw_data, f"fail {record.video_id} {exc}")
            finished_at = finish_run_event(
                events,
                stage="transcribe",
                item_id=record.video_id,
                status="failed",
                started_at=event_started_at,
                message=f"transcribe failed {record.video_id}",
                error=str(exc),
            )
            say(
                f"[{index}/{len(records)}] transcribe failed {record.video_id} "
                f"at {format_wall_time(finished_at)} in {elapsed}: {exc}"
            )
            continue

        elapsed = format_elapsed(time.monotonic() - item_started_at)
        if result.skipped:
            skipped += 1
            status = "skipped"
            message = f"transcribe skipped {record.video_id}"
        else:
            created += 1
            status = "success"
            message = f"transcribed {record.video_id}"
        finished_at = finish_run_event(
            events,
            stage="transcribe",
            item_id=record.video_id,
            status=status,
            started_at=event_started_at,
            message=message,
        )
        if result.skipped:
            say(
                f"[{index}/{len(records)}] transcribe skip {record.video_id} "
                f"at {format_wall_time(finished_at)} in {elapsed}: {result.paths.txt_path}"
            )
        else:
            say(
                f"[{index}/{len(records)}] transcribed {record.video_id} "
                f"at {format_wall_time(finished_at)} in {elapsed}: {result.paths.txt_path}"
            )

    total_elapsed = format_elapsed(time.monotonic() - batch_started_at)
    say(
        f"Transcription complete in {total_elapsed}: "
        f"created={created}, skipped={skipped}, failed={failed}"
    )
    return 1 if failed else 0


def chunk_transcripts(config: PipelineConfig, chunk_minutes: int, overlap_seconds: int) -> int:
    ensure_raw_layout(config.paths.raw_data)
    records = read_manifest(config.paths.raw_data)
    if not records:
        say("No videos in manifest.")
        say("Run `python3 -m media_to_wiki_convertor discover` or `import-list` first.")
        return 0

    chunk_seconds = chunk_minutes * 60
    if chunk_seconds <= 0:
        say("--chunk-minutes must be positive.")
        return 1
    if overlap_seconds < 0:
        say("--overlap-seconds must not be negative.")
        return 1
    if overlap_seconds >= chunk_seconds:
        say("--overlap-seconds must be smaller than --chunk-minutes.")
        return 1

    created = 0
    skipped = 0
    failed = 0
    say(
        "Chunking settings: "
        f"chunk_minutes={chunk_minutes}, "
        f"overlap_seconds={overlap_seconds}"
    )
    for index, record in enumerate(records, start=1):
        started_at = time.monotonic()
        say(f"[{index}/{len(records)}] chunk start {record.video_id}: {record.title}")
        try:
            result = chunk_transcript_record(
                record,
                config.paths.raw_data,
                chunk_seconds=chunk_seconds,
                overlap_seconds=overlap_seconds,
                on_progress=lambda message: say(f"  {message}"),
            )
        except Exception as exc:
            failed += 1
            elapsed = format_elapsed(time.monotonic() - started_at)
            say(f"[{index}/{len(records)}] chunk failed {record.video_id} in {elapsed}: {exc}")
            continue

        if result.skipped:
            skipped += 1
        else:
            created += result.created
        elapsed = format_elapsed(time.monotonic() - started_at)
        if result.skipped:
            say(
                f"[{index}/{len(records)}] chunk skip {record.video_id} "
                f"in {elapsed}: chunks={result.created}, dir={result.output_dir}"
            )
        else:
            say(
                f"[{index}/{len(records)}] chunked {record.video_id} "
                f"in {elapsed}: chunks={result.created}, dir={result.output_dir}"
            )

    say(f"Chunking complete: created_chunks={created}, skipped_videos={skipped}, failed={failed}")
    return 1 if failed else 0


def add_chunk_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--chunk-minutes",
        type=int,
        default=10,
        help="Target chunk window in minutes. Default: 10.",
    )
    parser.add_argument(
        "--overlap-seconds",
        type=int,
        default=120,
        help="Overlap between adjacent chunks in seconds. Default: 120.",
    )


def extract_knowledge(
    config: PipelineConfig,
    model: str | None,
    limit: int | None,
    sample_per_video: int | None,
    force: bool,
    dry_run: bool,
) -> int:
    ensure_raw_layout(config.paths.raw_data)
    try:
        payloads = select_chunk_payloads(
            chunk_payloads(config.paths.raw_data),
            limit=limit,
            sample_per_video=sample_per_video,
        )
    except ValueError as exc:
        say(str(exc))
        return 1

    if not payloads:
        say("No chunk JSON files found.")
        say("Run `python3 -m media_to_wiki_convertor chunk-transcripts` first.")
        return 0

    selected_model = model or config.llm.model
    say(
        "Knowledge extraction settings: "
        f"model={selected_model}, output_language={config.wiki.language}, "
        f"chunks={len(payloads)}, force={force}, dry_run={dry_run}"
    )

    if dry_run:
        say(build_extraction_prompt(payloads[0], output_language=config.wiki.language))
        return 0

    try:
        client = OpenAIKnowledgeClient.from_env(
            model=selected_model,
            output_language=config.wiki.language,
        )
    except RuntimeError as exc:
        say(str(exc))
        return 1
    created = 0
    skipped = 0
    failed = 0
    events = RunEventWriter(config.paths.raw_data)
    batch_started_at = time.monotonic()

    for index, payload in enumerate(payloads, start=1):
        started_at = time.monotonic()
        video_id = str(payload["video_id"])
        chunk_id = str(payload["chunk_id"])
        item_id = f"{video_id}/{chunk_id}"
        event_started_at = start_run_event(
            events,
            "extract-knowledge",
            item_id,
            f"knowledge start {item_id}",
        )
        say(
            f"[{index}/{len(payloads)}] knowledge start {item_id} "
            f"at {format_wall_time(event_started_at)}"
        )
        try:
            result = extract_chunk_knowledge(
                config.paths.raw_data,
                payload,
                client,
                force=force,
            )
        except Exception as exc:
            failed += 1
            elapsed = format_elapsed(time.monotonic() - started_at)
            finished_at = finish_run_event(
                events,
                stage="extract-knowledge",
                item_id=item_id,
                status="failed",
                started_at=event_started_at,
                message=f"knowledge failed {item_id}",
                error=str(exc),
            )
            say(
                f"[{index}/{len(payloads)}] knowledge failed {item_id} "
                f"at {format_wall_time(finished_at)} in {elapsed}: {exc}"
            )
            continue

        elapsed = format_elapsed(time.monotonic() - started_at)
        if result.skipped:
            skipped += 1
            status = "skipped"
            message = f"knowledge skipped {item_id}"
        else:
            created += 1
            status = "success"
            message = f"knowledge extracted {item_id}"
        finished_at = finish_run_event(
            events,
            stage="extract-knowledge",
            item_id=item_id,
            status=status,
            started_at=event_started_at,
            message=message,
        )
        if result.skipped:
            say(
                f"[{index}/{len(payloads)}] knowledge skip {item_id} "
                f"at {format_wall_time(finished_at)} in {elapsed}: {result.output_path}"
            )
        else:
            say(
                f"[{index}/{len(payloads)}] knowledge extracted {item_id} "
                f"at {format_wall_time(finished_at)} in {elapsed}: {result.output_path}"
            )

    total_elapsed = format_elapsed(time.monotonic() - batch_started_at)
    say(
        f"Knowledge extraction complete in {total_elapsed}: "
        f"created={created}, skipped={skipped}, failed={failed}"
    )
    return 1 if failed else 0


def build_topic_index(config: PipelineConfig) -> int:
    ensure_raw_layout(config.paths.raw_data)
    payloads = read_knowledge_payloads(config.paths.raw_data)
    if not payloads:
        say("No extracted knowledge JSON files found.")
        say("Run `python3 -m media_to_wiki_convertor extract-knowledge` first.")
        return 0

    started_at = time.monotonic()
    say(f"Topic index start: knowledge_files={len(payloads)}")
    index = build_topic_index_payload(payloads)
    output_dir = write_topic_index(config.paths.raw_data, index)
    elapsed = format_elapsed(time.monotonic() - started_at)
    say(
        "Topic index complete "
        f"in {elapsed}: "
        f"topics={index['summary']['topics']}, "
        f"terms={index['summary']['terms']}, "
        f"wiki_candidates={index['summary']['wiki_candidates']}, "
        f"pages={index['summary']['pages']}"
    )
    say(f"Wrote topic index: {output_dir}")
    return 0


def build_article_plan(config: PipelineConfig, min_sources: int, max_pages: int | None) -> int:
    ensure_raw_layout(config.paths.raw_data)
    try:
        pages = read_topic_pages(config.paths.raw_data)
        plan = build_article_plan_payload(pages, min_sources=min_sources, max_pages=max_pages)
    except ValueError as exc:
        say(str(exc))
        return 1

    if not pages:
        say("No topic index pages found.")
        say("Run `python3 -m media_to_wiki_convertor build-topic-index` first.")
        return 0

    started_at = time.monotonic()
    say(
        "Article plan start: "
        f"topic_pages={len(pages)}, min_sources={min_sources}, max_pages={max_pages}"
    )
    output_dir = write_article_plan(config.paths.raw_data, plan)
    elapsed = format_elapsed(time.monotonic() - started_at)
    say(
        "Article plan complete "
        f"in {elapsed}: "
        f"article_pages={plan['summary']['article_pages']}, "
        f"deferred_pages={plan['summary']['deferred_pages']}"
    )
    say(f"Wrote article plan: {output_dir}")
    return 0


def draft_articles(
    config: PipelineConfig,
    model: str | None,
    limit: int | None,
    force: bool,
    dry_run: bool,
) -> int:
    ensure_raw_layout(config.paths.raw_data)
    try:
        pages = read_article_pages(config.paths.raw_data)
        source_packs = select_source_packs(config.paths.raw_data, pages, limit=limit)
    except ValueError as exc:
        say(str(exc))
        return 1

    if not pages:
        say("No article plan pages found.")
        say("Run `python3 -m media_to_wiki_convertor build-article-plan` first.")
        return 0
    if not source_packs:
        say("No source packs found.")
        say("Run `python3 -m media_to_wiki_convertor build-article-plan` first.")
        return 0

    selected_model = model or config.llm.model
    known_titles = [str(page["title"]) for page in pages]
    say(
        "Draft articles settings: "
        f"model={selected_model}, output_language={config.wiki.language}, "
        f"articles={len(source_packs)}, force={force}, dry_run={dry_run}"
    )

    if dry_run:
        say(build_article_prompt(source_packs[0], known_titles, output_language=config.wiki.language))
        return 0

    try:
        client = OpenAIArticleClient.from_env(
            model=selected_model,
            output_language=config.wiki.language,
        )
    except RuntimeError as exc:
        say(str(exc))
        return 1

    created = 0
    skipped = 0
    failed = 0
    events = RunEventWriter(config.paths.raw_data)
    batch_started_at = time.monotonic()
    for index, source_pack in enumerate(source_packs, start=1):
        started_at = time.monotonic()
        article = source_pack["article"]
        title = str(article["title"])
        event_started_at = start_run_event(
            events,
            "draft-articles",
            title,
            f"draft start {title}",
        )
        say(
            f"[{index}/{len(source_packs)}] draft start {title} "
            f"at {format_wall_time(event_started_at)}"
        )
        try:
            result = draft_article(
                config.paths.raw_data,
                source_pack,
                client,
                known_titles,
                force=force,
            )
        except Exception as exc:
            failed += 1
            elapsed = format_elapsed(time.monotonic() - started_at)
            finished_at = finish_run_event(
                events,
                stage="draft-articles",
                item_id=title,
                status="failed",
                started_at=event_started_at,
                message=f"draft failed {title}",
                error=str(exc),
            )
            say(
                f"[{index}/{len(source_packs)}] draft failed {title} "
                f"at {format_wall_time(finished_at)} in {elapsed}: {exc}"
            )
            continue

        elapsed = format_elapsed(time.monotonic() - started_at)
        if result.skipped:
            skipped += 1
            status = "skipped"
            message = f"draft skipped {title}"
        else:
            created += 1
            status = "success"
            message = f"drafted {title}"
        finished_at = finish_run_event(
            events,
            stage="draft-articles",
            item_id=title,
            status=status,
            started_at=event_started_at,
            message=message,
        )
        if result.skipped:
            say(
                f"[{index}/{len(source_packs)}] draft skip {title} "
                f"at {format_wall_time(finished_at)} in {elapsed}: {result.output_path}"
            )
        else:
            say(
                f"[{index}/{len(source_packs)}] drafted {title} "
                f"at {format_wall_time(finished_at)} in {elapsed}: {result.output_path}"
            )

    total_elapsed = format_elapsed(time.monotonic() - batch_started_at)
    say(
        f"Draft articles complete in {total_elapsed}: "
        f"created={created}, skipped={skipped}, failed={failed}"
    )
    return 1 if failed else 0


def build_vault(config: PipelineConfig) -> int:
    ensure_raw_layout(config.paths.raw_data)
    started_at = time.monotonic()
    events = RunEventWriter(config.paths.raw_data)
    event_started_at = start_run_event(events, "build-vault", "vault", "vault build start")
    say(f"Vault build start at {format_wall_time(event_started_at)}: {config.paths.vault}")
    try:
        result = build_obsidian_vault(config.paths.raw_data, config.paths.vault)
    except Exception as exc:
        elapsed = format_elapsed(time.monotonic() - started_at)
        finished_at = finish_run_event(
            events,
            stage="build-vault",
            item_id="vault",
            status="failed",
            started_at=event_started_at,
            message="vault build failed",
            error=str(exc),
        )
        say(f"Vault build failed at {format_wall_time(finished_at)} in {elapsed}: {exc}")
        say(str(exc))
        return 1

    elapsed = format_elapsed(time.monotonic() - started_at)
    finished_at = finish_run_event(
        events,
        stage="build-vault",
        item_id="vault",
        status="success",
        started_at=event_started_at,
        message="vault build complete",
    )
    say(
        "Vault build complete "
        f"at {format_wall_time(finished_at)} in {elapsed}: "
        f"articles={result.articles}, "
        f"source_notes={result.source_notes}, "
        f"transcript_notes={result.transcript_notes}, "
        f"indexes={result.indexes}"
    )
    return 0


def pipeline_stages() -> dict[str, PipelineStage]:
    return {
        "discover": PipelineStage("discover", lambda config: discover(config)),
        "extract-audio": PipelineStage("extract-audio", lambda config: extract_audio(config)),
        "validate-audio": PipelineStage("validate-audio", lambda config: validate_audio(config)),
        "transcribe": PipelineStage("transcribe", lambda config: transcribe(config)),
        "chunk-transcripts": PipelineStage(
            "chunk-transcripts",
            lambda config: chunk_transcripts(
                config,
                config.chunking.chunk_minutes,
                config.chunking.overlap_seconds,
            ),
        ),
        "extract-knowledge": PipelineStage(
            "extract-knowledge",
            lambda config: extract_knowledge(config, None, None, None, False, False),
            expensive=True,
        ),
        "build-topic-index": PipelineStage("build-topic-index", lambda config: build_topic_index(config)),
        "build-article-plan": PipelineStage(
            "build-article-plan",
            lambda config: build_article_plan(config, min_sources=2, max_pages=None),
        ),
        "draft-articles": PipelineStage(
            "draft-articles",
            lambda config: draft_articles(config, None, None, False, False),
            expensive=True,
        ),
        "build-vault": PipelineStage("build-vault", lambda config: build_vault(config)),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="media-to-wiki-convertor")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.toml. Defaults to ./config.toml, then ./config.example.toml.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a new media-to-wiki-convertor project folder.")
    init_parser.add_argument("project_dir", type=Path)
    init_parser.add_argument("--force", action="store_true")

    config_parser = subparsers.add_parser("config", help="Update config.toml project settings.")
    config_parser.add_argument("--videos", type=Path, default=None)
    config_parser.add_argument("--raw", type=Path, default=None)
    config_parser.add_argument("--vault", type=Path, default=None)
    config_parser.add_argument("--language", default=None)

    run_parser = subparsers.add_parser("run", help="Run the full pipeline in order.")
    run_parser.add_argument("--from", dest="from_stage", default=None)
    run_parser.add_argument("--to", dest="to_stage", default=None)
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--yes", action="store_true")

    subparsers.add_parser("status", help="Show configured paths and current manifest count.")
    discover_parser = subparsers.add_parser(
        "discover",
        help="Scan the read-only video source and write manifest.",
    )
    discover_parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Override video source directory for this run.",
    )
    import_parser = subparsers.add_parser(
        "import-list",
        help="Build manifest from a text file containing one video path per line.",
    )
    import_parser.add_argument(
        "--file",
        type=Path,
        required=True,
        help="Text file with absolute paths or names relative to --base.",
    )
    import_parser.add_argument(
        "--base",
        type=Path,
        default=None,
        help="Base directory for relative paths. Defaults to configured video_source.",
    )
    import_transcript_parser = subparsers.add_parser(
        "import-transcript",
        help="Import an existing JSON or TXT transcript into raw-data/transcripts.",
    )
    import_transcript_parser.add_argument("--video-id", required=True)
    import_transcript_parser.add_argument(
        "--file",
        type=Path,
        required=True,
        help="Transcript file to import. Supports .json and .txt.",
    )
    import_transcript_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing complete transcript set.",
    )
    subparsers.add_parser("extract-audio", help="Extract mono 16 kHz WAV files with ffmpeg.")
    subparsers.add_parser("validate-audio", help="Validate extracted WAV files with ffprobe.")
    subparsers.add_parser("transcribe", help="Transcribe WAV files with local mlx-whisper.")
    chunk_parser = subparsers.add_parser(
        "chunk-transcripts",
        help="Split transcript JSON files into overlapping chunk JSON/Markdown files.",
    )
    add_chunk_arguments(chunk_parser)
    chunk_alias_parser = subparsers.add_parser("chunk", help="Alias for chunk-transcripts.")
    add_chunk_arguments(chunk_alias_parser)
    knowledge_parser = subparsers.add_parser(
        "extract-knowledge",
        help="Extract structured knowledge JSON from transcript chunks with OpenAI.",
    )
    knowledge_parser.add_argument(
        "--model",
        default=None,
        help="OpenAI model. Defaults to [llm].model in config.",
    )
    knowledge_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N chunks. Useful for a cheap trial run.",
    )
    knowledge_parser.add_argument(
        "--sample-per-video",
        type=int,
        default=None,
        help="Process the first N chunks from each video. Useful for a diverse trial run.",
    )
    knowledge_parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild existing extracted knowledge files.",
    )
    knowledge_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the first extraction prompt without calling the API.",
    )
    subparsers.add_parser(
        "build-topic-index",
        help="Build deterministic topic/page indexes from extracted knowledge JSON.",
    )
    article_plan_parser = subparsers.add_parser(
        "build-article-plan",
        help="Build deterministic article plan and source packs from topic index pages.",
    )
    article_plan_parser.add_argument(
        "--min-sources",
        type=int,
        default=2,
        help="Minimum distinct source chunks required for an article page. Default: 2.",
    )
    article_plan_parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Keep only the top N article pages by deterministic score.",
    )
    draft_articles_parser = subparsers.add_parser(
        "draft-articles",
        help="Draft Markdown wiki articles from article source packs with OpenAI.",
    )
    draft_articles_parser.add_argument(
        "--model",
        default=None,
        help="OpenAI model. Defaults to [llm].model in config.",
    )
    draft_articles_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Draft only the first N articles from article_plan/pages.json.",
    )
    draft_articles_parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild existing draft article Markdown files.",
    )
    draft_articles_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the first article prompt without calling the API.",
    )
    subparsers.add_parser("summarize", help="Planned low-token summarization stage.")
    subparsers.add_parser("build-vault", help="Build the Obsidian vault from drafted articles.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "init":
        try:
            result = init_project(args.project_dir, force=args.force)
        except FileExistsError as exc:
            say(str(exc))
            return 1
        say(f"Created media-to-wiki-convertor project: {result.project_dir}")
        return 0

    if args.command == "config":
        update_project_config(
            Path("config.toml"),
            ProjectSettings(
                videos=args.videos,
                raw=args.raw,
                vault=args.vault,
                language=args.language,
            ),
        )
        say("Updated config.toml")
        return 0

    config = load_config(args.config)

    if args.command == "run":
        return run_selected_stages(
            config,
            pipeline_stages(),
            from_stage=args.from_stage,
            to_stage=args.to_stage,
            assume_yes=args.yes,
            dry_run=args.dry_run,
            say=say,
        )

    if args.command == "status":
        print_status(config)
        return 0
    if args.command == "discover":
        discover(config, args.source)
        return 0
    if args.command == "import-list":
        import_video_list(config, args.file, args.base)
        return 0
    if args.command == "import-transcript":
        return import_transcript(config, args.video_id, args.file, args.force)
    if args.command == "extract-audio":
        return extract_audio(config)
    if args.command == "validate-audio":
        return validate_audio(config)
    if args.command == "transcribe":
        return transcribe(config)
    if args.command in {"chunk-transcripts", "chunk"}:
        return chunk_transcripts(config, args.chunk_minutes, args.overlap_seconds)
    if args.command == "extract-knowledge":
        return extract_knowledge(
            config,
            args.model,
            args.limit,
            args.sample_per_video,
            args.force,
            args.dry_run,
        )
    if args.command == "build-topic-index":
        return build_topic_index(config)
    if args.command == "build-article-plan":
        return build_article_plan(config, args.min_sources, args.max_pages)
    if args.command == "draft-articles":
        return draft_articles(config, args.model, args.limit, args.force, args.dry_run)
    if args.command == "build-vault":
        return build_vault(config)

    planned_stage(args.command)
    return 0
