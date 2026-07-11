# Media-First Technical Debt Backlog

Created: 2026-07-11

## Context

The product now supports video and audio recordings as media inputs. The public README and default discovery extensions already mention common audio formats, but several compatibility-era names still expose "video" terminology to new users and future maintainers.

This backlog keeps the cleanup incremental. Existing projects and raw-data artifacts must continue to work.

## Task 1: Add media-source config CLI alias

Status: completed

Problem:
- `media-to-wiki-convertor config` still exposes only `--videos`.
- New audio-first users should not have to pass a video-named option.

Contract:
- Add `--media-source` as the preferred CLI option.
- Keep `--videos` as a backward-compatible alias.
- If both are passed, `--media-source` wins.
- `config.toml` may continue using `[paths].video_source` internally for compatibility.

Acceptance:
- Parser accepts `config --media-source ./recordings`.
- `config --media-source ./recordings` writes `video_source = "./recordings"`.
- `config --videos ./videos` still works.
- Tests document precedence when both options are provided.

## Task 2: Add media-first config/model aliases

Status: completed

Problem:
- `PipelinePaths.video_source` and `DiscoverConfig.video_extensions` are still the only Python attribute names.
- New implementation code will keep spreading video terminology.

Contract:
- Add read-only `PipelinePaths.media_source` property.
- Add read-only `DiscoverConfig.media_extensions` property.
- Keep old attributes as canonical storage for compatibility.
- Internal new code should prefer media aliases where practical.

Acceptance:
- Tests prove media alias properties return the same values.
- CLI status/discover/import-list uses `media_source` and `media_extensions`.
- No persisted config shape changes.

## Task 3: Add media-first manifest API aliases

Status: completed

Problem:
- Public helpers are named `VideoRecord`, `iter_video_files`, `read_video_path_list`, `build_video_record`, and `stable_video_id`.
- Manifest records still use `video_id`, which is deeply embedded in chunk/source artifacts.

Contract:
- Add compatibility-safe aliases:
  - `MediaRecord = VideoRecord`
  - `stable_media_id(...)`
  - `iter_media_files(...)`
  - `read_media_path_list(...)`
  - `build_media_record(...)`
- Keep persisted field `video_id` and `manifest/videos.jsonl` unchanged for now.

Acceptance:
- Tests cover audio file discovery through `iter_media_files`.
- Tests cover path-list import through `read_media_path_list`.
- Existing video-named helpers still pass current tests.

## Task 4: Strengthen audio-only fixtures

Status: pending

Problem:
- Audio support is currently protected mostly by config/default tests.
- Most fixtures still use `.mp4`, so regressions in audio input handling could slip through.

Contract:
- Add tests with `.m4a` or `.mp3` media paths for manifest, audio extraction command construction, and project config examples.
- Do not require real media files or ffmpeg execution in tests.

Acceptance:
- Audio-only source files can be discovered and converted into manifest records.
- Audio input paths are passed to the same ffmpeg extraction path.

## Task 5: Documentation cleanup for media-first UX

Status: pending

Problem:
- README still shows `--videos "/path/to/videos"` and describes folders of training videos first.
- Compatibility naming is explained, but the first-run path should be media-first.

Contract:
- README quickstart should use `--media-source`.
- Compatibility note should mention `--videos` as legacy alias.
- CHANGELOG should mention media-first aliases.

Acceptance:
- README contains `--media-source`.
- README no longer presents `--videos` as the primary command.
- Changelog captures the migration.

## Deferred: manifest schema migration

Status: deferred

Problem:
- `manifest/videos.jsonl` and `video_id` are legacy names.

Decision:
- Do not migrate persisted schema in this debt cleanup epic. It would require artifact migration across chunks, transcripts, knowledge JSON, source packs, vault source links, and existing user projects.
- Revisit only as a separate versioned migration plan.
