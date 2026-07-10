# media-to-wiki-convertor

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![CLI](https://img.shields.io/badge/interface-CLI-2ea44f)](#quickstart)
[![Obsidian](https://img.shields.io/badge/output-Obsidian%20vault-7c3aed)](#generated-output)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Tests](https://github.com/TimurTsedik/media-to-wiki-convertor/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/TimurTsedik/media-to-wiki-convertor/actions/workflows/test.yml)

Turn long videos into a searchable Obsidian wiki.

`media-to-wiki-convertor` is a local-first CLI pipeline for converting folders of training videos, calls, lectures, workshops, or research recordings into structured notes with source links.

It does the boring heavy lifting:

- discovers media files
- extracts audio
- transcribes locally with Whisper on Apple Silicon
- imports existing JSON or TXT transcripts
- splits transcripts into overlapping chunks
- extracts structured knowledge with the configured LLM provider
- builds a high-level catalog from planned and deferred topics
- builds course reference chapters from catalog topics
- drafts wiki articles
- drafts course reference materials
- builds an Obsidian vault with links back to chunks and transcripts

## Why This Exists

Long recordings are full of useful knowledge, but raw transcripts are a swamp. This project turns the swamp into a map: articles, indexes, source notes, and transcript references that are easy to browse, search, and improve inside Obsidian.

## Pipeline

```text
videos
  -> audio
  -> transcripts
  -> overlapping chunks
  -> structured knowledge
  -> article plan
  -> catalog
  -> course materials plan
  -> drafted wiki pages
  -> drafted course materials
  -> Obsidian vault
```

Every stage writes files to disk, so the pipeline is resumable. If a run stops halfway through, fix the problem and rerun the next command.

## Recent Updates

This project has already absorbed its first round of real user feedback:

- Windows-friendly transcript import: use `import-transcript` when `mlx-whisper` is unavailable or when transcripts already exist.
- Untimed text transcripts: plain `.txt` imports are chunked by word windows with overlap, without inventing fake timestamps.
- Separate language settings: `[transcription].language` controls speech/transcript language, while `[wiki].language` controls extracted knowledge and drafted article language.
- Run telemetry: long-running stages write support-friendly JSONL events to `raw-data/logs/run-events.jsonl` with start, finish, elapsed time, status, and errors.
- LLM provider configuration: choose OpenAI, Anthropic, Gemini, or an OpenAI-compatible endpoint with provider-specific API key env vars.

## Requirements

- Python 3.11+
- `ffmpeg`
- macOS Apple Silicon for the default `mlx-whisper` transcription engine, unless you import transcripts
- API key for the configured LLM provider, for knowledge extraction and article drafting

Install `ffmpeg` on macOS:

```bash
brew install ffmpeg
```

## Install For Development

```bash
git clone https://github.com/TimurTsedik/media-to-wiki-convertor.git
cd media-to-wiki-convertor

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[mlx,dev]'
```

Check the CLI:

```bash
.venv/bin/media-to-wiki-convertor --help
```

## Quickstart

Create a separate project folder for your media conversion run:

```bash
media-to-wiki-convertor init my-training
cd my-training
cp .env.example .env
```

Add the API key for your configured LLM provider to `.env`:

```text
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
```

The default LLM configuration uses OpenAI:

```toml
[llm]
provider = "openai"
model = "gpt-5.4-mini"
base_url = "https://api.openai.com/v1/responses"
api_key_env = "OPENAI_API_KEY"
```

Supported providers are `openai`, `openai-compatible`, `anthropic`, and `gemini`.

For Anthropic:

```toml
[llm]
provider = "anthropic"
model = "claude-3-5-sonnet-latest"
base_url = "https://api.anthropic.com/v1/messages"
api_key_env = "ANTHROPIC_API_KEY"
```

For Gemini, keep `{model}` in the URL so the configured model can be inserted:

```toml
[llm]
provider = "gemini"
model = "gemini-1.5-pro"
base_url = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
api_key_env = "GEMINI_API_KEY"
```

For an OpenAI-compatible endpoint, point `base_url` and `api_key_env` at that service:

```toml
[llm]
provider = "openai-compatible"
model = "provider-model-name"
base_url = "https://example.com/v1/responses"
api_key_env = "COMPATIBLE_LLM_API_KEY"
```

Configure paths:

```bash
media-to-wiki-convertor config \
  --videos "/path/to/videos" \
  --raw "./raw-data" \
  --vault "./vault" \
  --language ru
```

Language settings are split by purpose in `config.toml`:

```toml
[transcription]
language = "en"

[wiki]
language = "en"
```

`[transcription].language` is passed to the transcription engine. `[wiki].language` controls the language used for extracted knowledge and drafted articles.

Inspect the plan before spending compute or API budget:

```bash
media-to-wiki-convertor status
media-to-wiki-convertor run --dry-run
```

Run the pipeline:

```bash
media-to-wiki-convertor run --yes
```

On Windows, or on any machine where `mlx-whisper` is not available, use an existing transcript instead of the local transcription stage:

```bash
media-to-wiki-convertor discover
media-to-wiki-convertor import-transcript --video-id VIDEO_ID --file transcript.txt
media-to-wiki-convertor chunk-transcripts
media-to-wiki-convertor extract-knowledge --sample-per-video 1
media-to-wiki-convertor build-topic-index
media-to-wiki-convertor build-article-plan
media-to-wiki-convertor build-catalog
media-to-wiki-convertor build-course-plan
media-to-wiki-convertor draft-articles
media-to-wiki-convertor draft-course-materials --limit 3
media-to-wiki-convertor build-vault
```

`import-transcript` supports the internal JSON transcript format, Whisper-like JSON with top-level `segments`, and plain `.txt`. Plain text imports are marked as untimed, so chunk/source metadata will not pretend to have exact timestamps.

For untimed `.txt` imports, `chunk-transcripts` uses the same numeric chunk settings as word windows: `--chunk-minutes 600 --overlap-seconds 120` means 600 words with 120 words of overlap. Timestamped JSON transcripts still use time windows.

## Stage Commands

You can also run stages one by one.

| Stage | What It Does |
| --- | --- |
| `discover` | Scans the video folder and builds a manifest. |
| `import-list` | Builds a manifest from a text file of media paths. |
| `import-transcript` | Imports an existing JSON or TXT transcript for a manifest video. |
| `extract-audio` | Extracts mono 16 kHz WAV audio with `ffmpeg`. |
| `validate-audio` | Checks extracted audio files before transcription. |
| `transcribe` | Transcribes audio locally with `mlx-whisper`. |
| `chunk-transcripts` | Splits transcript JSON into overlapping chunk files. |
| `extract-knowledge` | Uses the configured LLM provider to extract topics, terms, practices, and article candidates. |
| `build-topic-index` | Builds deterministic indexes from extracted knowledge. |
| `build-article-plan` | Selects article pages and source packs. Defaults to keeping single-source topics; use `--min-sources 2` for stricter filtering. |
| `build-catalog` | Groups planned articles and deferred topics into deterministic catalog categories with merge suggestions. |
| `build-course-plan` | Builds deterministic course reference chapters from catalog categories, existing articles, and deferred topics. |
| `draft-articles` | Uses the configured LLM provider to draft wiki article Markdown. |
| `draft-course-materials` | Uses the configured LLM provider to draft course reference chapter Markdown. |
| `build-vault` | Builds the final Obsidian vault. |

Example:

```bash
media-to-wiki-convertor discover
media-to-wiki-convertor extract-audio
media-to-wiki-convertor transcribe
media-to-wiki-convertor chunk-transcripts
media-to-wiki-convertor extract-knowledge --sample-per-video 1
media-to-wiki-convertor build-topic-index
media-to-wiki-convertor build-article-plan
media-to-wiki-convertor build-catalog
media-to-wiki-convertor build-course-plan
media-to-wiki-convertor draft-articles
media-to-wiki-convertor draft-course-materials --limit 3
media-to-wiki-convertor build-vault
```

## Cost And Privacy

Transcription is local. Your media and audio do not need to leave your machine for the transcription stage.

These stages send transcript-derived text to the configured LLM provider:

- `extract-knowledge`
- `draft-articles`

Use trial runs before sending everything:

```bash
media-to-wiki-convertor extract-knowledge --sample-per-video 1 --dry-run
media-to-wiki-convertor draft-articles --limit 1 --dry-run
```

## Generated Output

A project created with `init` looks like this:

```text
my-training/
  config.toml
  .env
  .env.example
  raw-data/
  vault/
```

Generated files are ignored by default:

- `.env`
- `raw-data/`
- `vault/`

The vault contains:

- `00 Home.md`
- `Course Materials/`
- `Index/`
- `Index/Catalog/`
- `Wiki/`
- `Sources/`
- `90 Transcripts.md`
- `90 Transcripts/`

## Testing

```bash
.venv/bin/python -m pytest -q
```

Expected result:

```text
126 passed
```

## Notes

The default transcription engine is optimized for Apple Silicon via `mlx-whisper`. Other engines can be added later behind the same file-based pipeline.
Users who already have transcripts can skip `extract-audio` and `transcribe` by importing transcript files directly.
