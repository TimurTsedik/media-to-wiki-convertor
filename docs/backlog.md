# Backlog

This backlog converts user feedback and product discoveries into durable implementation slices.

## 2026-07-10: First External User Feedback

Raw feedback:

- Windows users cannot use the default `mlx-whisper` transcription engine.
- Some users already have transcripts from another transcription tool and need to import them.
- Long-running stages should show and persist clear timing: started at, finished at, elapsed.
- Users want to choose the AI service/provider, not only the default OpenAI client.
- A user set `language = "en"` in `config.toml`, but the result behaved as if it was ignored.

System status:

- `import-transcript` is a product workflow, not a workaround.
- `mlx-whisper` remains the default local transcription engine for Apple Silicon, but it must not be a required step for users with existing transcripts.
- Timing is operational telemetry and support evidence.
- `[llm].provider` already exists in config but is not enforced by a provider factory.
- Language currently mixes transcript language and wiki output language. These must become separate config concepts.

## Tasks

### MTW-001: Make Language Configuration Explicit

Status: Done

Contract:

- `[transcription].language` controls speech/transcript language passed to the transcription engine.
- `[wiki].language` controls the language used by knowledge extraction and article drafting prompts.
- A top-level `language = "..."` remains a deprecated compatibility alias and must not be silently ignored.
- CLI `config --language en` updates both transcript and wiki language until separate CLI flags exist.

Acceptance criteria:

- Loading config with `[transcription].language = "en"` yields `config.transcription.language == "en"`.
- Loading config with `[wiki].language = "en"` yields `config.wiki.language == "en"`.
- Loading config with top-level `language = "en"` sets both values to `"en"` when the specific sections are missing.
- Knowledge and article prompts include the configured output language instruction.
- Tests cover all cases above.

Audit:

- Risk: prompt wording changes may affect output quality.
- Risk: current Russian-first defaults must remain unchanged for existing projects.
- Dependency: prompt builders currently do not receive config.
- Verification: unit tests for config and prompt text; full pytest.

Verification:

- `RUFF_CACHE_DIR=/tmp/media-wiki-ruff-cache /tmp/media-wiki-ci-venv/bin/python -m ruff check media_to_wiki_convertor tests` -> passed.
- `PYTHONPATH=... /tmp/media-wiki-ci-venv/bin/python -m pytest -q -p no:cacheprovider` -> 74 passed.

### MTW-002: Import Existing Transcripts

Status: Done

Contract:

- New command: `media-to-wiki-convertor import-transcript`.
- It imports user-provided transcript files into the internal transcript set:
  - `raw-data/transcripts/{video_id}.json`
  - `raw-data/transcripts/{video_id}.txt`
  - `raw-data/transcripts/{video_id}.srt`
- Supported MVP formats:
  - our JSON transcript format;
  - Whisper-like JSON with `segments`;
  - plain `.txt`.
- Plain text transcripts may have unknown timestamps. The internal JSON must mark this explicitly.

Acceptance criteria:

- User can import transcript by `--video-id`.
- User can import transcript by `--title` or manifest match later; MVP can require `--video-id`.
- Import skips existing complete transcript unless `--force`.
- Import writes all three transcript files.
- Status counts imported transcripts.
- README documents Windows path: `discover/import-list -> import-transcript -> chunk-transcripts -> ...`.

Audit:

- Risk: plain text has no timing, so source links cannot point to accurate timestamps.
- Risk: user-provided AI-converted JSON may be malformed.
- Dependency: chunker currently assumes numeric segment timestamps.
- Verification: parser tests for JSON and TXT; CLI smoke test.

Verification:

- Worker implemented import command and transcript parsers.
- Reviewer fixed completion semantics for untimed transcripts with empty `.srt`.
- `PYTHONPATH=... /tmp/media-wiki-ci-venv/bin/python -m pytest tests/test_transcription.py tests/test_chunks.py tests/test_cli.py -q -p no:cacheprovider` -> 20 passed.
- `PYTHONPATH=... /tmp/media-wiki-ci-venv/bin/python -m pytest -q -p no:cacheprovider` -> 79 passed.
- `RUFF_CACHE_DIR=/tmp/media-wiki-ruff-cache /tmp/media-wiki-ci-venv/bin/python -m ruff check media_to_wiki_convertor tests` -> passed.

### MTW-003: Chunk Transcripts Without Timestamps

Status: Done

Contract:

- Timestamped transcripts are chunked by time window as today.
- Untimed transcripts are chunked by text length with text overlap.
- Chunk metadata must state `chunking_mode = "time"` or `"text"`.
- Source timestamps for untimed chunks should be empty or marked unknown, not fabricated.

Acceptance criteria:

- Chunker detects untimed segments.
- Untimed transcript chunks are deterministic.
- Overlap works for text chunks.
- Downstream knowledge extraction can read untimed chunks.
- Vault/source notes do not pretend untimed source timestamps are exact.

Audit:

- Risk: article source references lose timestamp precision.
- Dependency: import-transcript TXT path.
- Verification: unit tests for text chunking and downstream chunk JSON shape.

Verification:

- Untimed transcripts are chunked with `chunking_mode = "text"`.
- Untimed chunks use unknown/empty timestamps instead of fabricated time ranges.
- README documents that untimed text chunks reuse chunk settings as word windows in this MVP.
- Same verification commands as MTW-002.

### MTW-004: Persist Stage Timing And Run Events

Status: Done

Contract:

- Every stage writes JSONL events to `raw-data/logs/run-events.jsonl`.
- Event fields:
  - `timestamp`;
  - `stage`;
  - `item_id`;
  - `status`: `started`, `skipped`, `success`, `failed`;
  - `started_at`;
  - `finished_at`;
  - `elapsed_seconds`;
  - `message`;
  - optional `error`.
- Console output includes wall-clock start/end for long-running item work.

Acceptance criteria:

- At least `extract-audio`, `transcribe`, `extract-knowledge`, `draft-articles`, and `build-vault` emit events.
- On failure, event includes error message and elapsed time.
- Existing plain text logs can remain, but JSONL is the support/debug source of truth.
- Tests cover event shape and one failed item.

Audit:

- Risk: too much logging noise; keep one event per meaningful state.
- Dependency: none, can be incremental.
- Verification: unit tests for event writer; CLI-level smoke where practical.

Verification:

- Worker added `RunEventWriter` JSONL support and instrumented core long-running stages.
- Reviewer expanded `build-vault` failure coverage to unexpected exceptions.
- `PYTHONPATH=... /tmp/media-wiki-ci-venv/bin/python -m pytest tests/test_run_events.py tests/test_cli.py -q -p no:cacheprovider` -> 5 passed.
- `PYTHONPATH=... /tmp/media-wiki-ci-venv/bin/python -m pytest -q -p no:cacheprovider` -> 83 passed.
- `RUFF_CACHE_DIR=/tmp/media-wiki-ruff-cache /tmp/media-wiki-ci-venv/bin/python -m ruff check media_to_wiki_convertor tests` -> passed.

### MTW-005: Add LLM Provider Factory

Status: Ready

Contract:

- `[llm].provider` controls which client implementation is created.
- Supported MVP:
  - `openai`;
  - `openai-compatible` with configurable `base_url` and API key env.
- Unsupported providers fail fast with a clear error before processing chunks.
- Knowledge extraction and article drafting use the same provider configuration.

Acceptance criteria:

- Existing OpenAI behavior stays unchanged.
- `provider = "openai"` creates OpenAI clients.
- `provider = "openai-compatible"` uses configured base URL and env var.
- Unsupported provider prints a clear CLI error.
- Tests cover client factory and CLI selection.

Audit:

- Risk: structured outputs are OpenAI-specific; provider compatibility must be explicit.
- Risk: non-OpenAI APIs may not support the Responses API shape.
- Dependency: current clients are tightly named `OpenAI...`.
- Verification: transport-injected tests, no live API calls.

## Execution Order

1. MTW-001: Language config and prompt language.
2. MTW-002: Import existing transcript MVP.
3. MTW-003: Text chunking for untimed transcripts.
4. MTW-004: JSONL run events.
5. MTW-005: LLM provider factory.

## Now

- Start MTW-005.

## Next

- MTW-002 and MTW-003 should ship together for Windows users with plain text transcripts.
