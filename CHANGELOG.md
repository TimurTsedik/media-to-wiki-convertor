# Changelog

## Unreleased

- Switch generated Obsidian vaults to a course-first numbered layout:
  `00 Start Here.md`, `01 Course Materials/`, `02 Reference Wiki/`, `03 Indexes/`,
  `04 Sources/`, `05 Transcripts/`, and `99 System/`.
- Treat common audio recordings as first-class media inputs by default via
  `[discover].media_extensions`, while keeping legacy `video_extensions` configs working.
- Add media-first compatibility aliases including `config --media-source`, config dataclass
  media properties, and manifest helper aliases.

## 1.0.3 - 2026-07-10

- Respect the global `--config` path for the `config` command.
- Use `[chunking]` defaults when `chunk-transcripts` is run without explicit chunk arguments.
- Add `healthcheck` to validate resumable chunk and knowledge artifacts before continuing a run.
- Retry transient LLM transport failures and 408/429/5xx responses.
- Remove old Larchenko branding from generated status/home text and localize deterministic vault headings.
- Expand CI to run ruff, Python 3.11/3.12 tests, CLI smoke checks, and package smoke checks.
- Document managed vault folders that are rewritten by `build-vault`.

## 1.0.2 - 2026-07-10

- Add a deterministic `build-catalog` stage that groups planned articles and deferred topics into higher-level catalog categories.
- Generate catalog JSON artifacts and Obsidian catalog indexes under `Index/Catalog/`.
- Add conservative merge suggestions for deferred topics that look like sections or aliases of planned articles.
- Link catalog topics back to source chunks and avoid empty wiki pages for deferred topics in source indexes.
- Add a deterministic `build-course-plan` stage and render `Course Materials/` pages in the vault.
- Add `draft-course-materials` for LLM-drafted course reference chapters.
- Localize generated course-material headings and source sections for English vaults.
- Expand README guidance for cost, article granularity, deferred topics, and course materials.

## 1.0.1 - 2026-07-10

Bugfix release.

- Keep single-source topics in the article plan by default, so rare but useful topics are sent to article drafting instead of being deferred.
- Keep stricter filtering available with `build-article-plan --min-sources 2`.

## 1.0.0 - 2026-07-10

Initial stable CLI release.

- Convert folders of media files into an Obsidian vault.
- Discover videos, extract audio, validate WAV files, and transcribe with local `mlx-whisper` on Apple Silicon.
- Import existing JSON or TXT transcripts for Windows and non-MLX workflows.
- Split transcripts into overlapping chunks, including untimed text transcript chunks.
- Extract structured knowledge and draft wiki articles with OpenAI, Anthropic, Gemini, or OpenAI-compatible LLM providers.
- Track long-running stage events in `raw-data/logs/run-events.jsonl`.
- Generate source-linked wiki articles, source notes, transcript links, and topic indexes.
