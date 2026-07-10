# Changelog

## 1.0.0 - 2026-07-10

Initial stable CLI release.

- Convert folders of media files into an Obsidian vault.
- Discover videos, extract audio, validate WAV files, and transcribe with local `mlx-whisper` on Apple Silicon.
- Import existing JSON or TXT transcripts for Windows and non-MLX workflows.
- Split transcripts into overlapping chunks, including untimed text transcript chunks.
- Extract structured knowledge and draft wiki articles with OpenAI, Anthropic, Gemini, or OpenAI-compatible LLM providers.
- Track long-running stage events in `raw-data/logs/run-events.jsonl`.
- Generate source-linked wiki articles, source notes, transcript links, and topic indexes.
