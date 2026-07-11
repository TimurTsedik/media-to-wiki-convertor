# Media-First Debt Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development for each behavior change. Execute task-by-task with verification and one commit per task.

**Goal:** Make media-first terminology available to users and maintainers while preserving existing config, manifest, and raw-data compatibility.

**Architecture:** Add aliases at the CLI/config/manifest boundaries before renaming internals. Persisted artifacts keep existing `video_source`, `video_id`, and `manifest/videos.jsonl` names until a separate versioned migration exists.

**Tech Stack:** Python 3.11+, argparse, dataclasses, pytest, ruff.

---

## Task 1: CLI media-source alias

**Files:**
- Modify: `media_to_wiki_convertor/cli.py`
- Modify: `media_to_wiki_convertor/project.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_project.py`
- Docs: `.agents/backlog/2026-07-11-media-first-debt.md`

Steps:

- [x] Write parser/config tests for `--media-source`.
- [x] Run focused tests and confirm they fail.
- [x] Add `--media-source` to the `config` command.
- [x] Preserve `--videos` and make `--media-source` take precedence.
- [x] Run focused tests and confirm they pass.
- [x] Update backlog task status.
- [x] Commit.

## Task 2: Config dataclass media aliases

**Files:**
- Modify: `media_to_wiki_convertor/config.py`
- Modify: `media_to_wiki_convertor/cli.py`
- Test: `tests/test_config.py`
- Test: `tests/test_cli.py`
- Docs: `.agents/backlog/2026-07-11-media-first-debt.md`

Steps:

- [x] Write tests for `PipelinePaths.media_source` and `DiscoverConfig.media_extensions`.
- [x] Run focused tests and confirm they fail.
- [x] Add read-only property aliases.
- [x] Switch CLI internals to use media aliases where possible.
- [x] Run focused tests and confirm they pass.
- [x] Update backlog task status.
- [x] Commit.

## Task 3: Manifest media aliases

**Files:**
- Modify: `media_to_wiki_convertor/manifest.py`
- Modify: `media_to_wiki_convertor/cli.py`
- Test: `tests/test_manifest.py`
- Docs: `.agents/backlog/2026-07-11-media-first-debt.md`

Steps:

- [x] Write tests for `MediaRecord`, `stable_media_id`, `iter_media_files`, `read_media_path_list`, and `build_media_record`.
- [x] Run focused tests and confirm they fail.
- [x] Add aliases/wrappers without changing persisted schema.
- [x] Switch CLI imports/calls to media aliases.
- [x] Run focused tests and confirm they pass.
- [x] Update backlog task status.
- [x] Commit.

## Task 4: Audio-only fixture coverage

**Files:**
- Modify: `tests/test_manifest.py`
- Modify: `tests/test_audio.py`
- Modify: `tests/test_project.py`
- Docs: `.agents/backlog/2026-07-11-media-first-debt.md`

Steps:

- [x] Add tests proving `.m4a` or `.mp3` source files are discovered/imported.
- [x] Add an audio extraction command test using an audio input path.
- [x] Run focused tests and confirm behavior is covered.
- [x] Update backlog task status.
- [x] Commit.

## Task 5: Docs and changelog cleanup

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Docs: `.agents/backlog/2026-07-11-media-first-debt.md`

Steps:

- [x] Update README quickstart to prefer `--media-source`.
- [x] Keep `--videos` documented as a legacy alias.
- [x] Update changelog.
- [x] Search docs for stale primary `--videos` wording.
- [x] Update backlog task status.
- [ ] Commit.

## Final Verification

Steps:

- [ ] Run `.venv/bin/python -m pytest -p no:cacheprovider -q`.
- [ ] Run `env RUFF_CACHE_DIR=/private/tmp/media-to-wiki-ruff-cache .venv/bin/python -m ruff check .`.
- [ ] Run `.venv/bin/media-to-wiki-convertor --help`.
- [ ] Push `main`.
- [ ] Check GitHub Actions.
