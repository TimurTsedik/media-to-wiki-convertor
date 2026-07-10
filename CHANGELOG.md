# Changelog

## Unreleased

- Add a deterministic `build-catalog` stage that groups planned articles and deferred topics into higher-level catalog categories.
- Generate catalog JSON artifacts and Obsidian catalog indexes under `Index/Catalog/`.
- Add conservative merge suggestions for deferred topics that look like sections or aliases of planned articles.
- Link catalog topics back to source chunks and avoid empty wiki pages for deferred topics in source indexes.
- Add a deterministic `build-course-plan` stage and render `Course Materials/` pages in the vault.

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
