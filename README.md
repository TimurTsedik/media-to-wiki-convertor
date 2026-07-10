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
- splits transcripts into overlapping chunks
- extracts structured knowledge with OpenAI
- drafts wiki articles
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
  -> drafted wiki pages
  -> Obsidian vault
```

Every stage writes files to disk, so the pipeline is resumable. If a run stops halfway through, fix the problem and rerun the next command.

## Requirements

- Python 3.11+
- `ffmpeg`
- macOS Apple Silicon for the default `mlx-whisper` transcription engine
- OpenAI API key for knowledge extraction and article drafting

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

Add your OpenAI API key to `.env`:

```text
OPENAI_API_KEY=
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

## Stage Commands

You can also run stages one by one.

| Stage | What It Does |
| --- | --- |
| `discover` | Scans the video folder and builds a manifest. |
| `import-list` | Builds a manifest from a text file of media paths. |
| `extract-audio` | Extracts mono 16 kHz WAV audio with `ffmpeg`. |
| `validate-audio` | Checks extracted audio files before transcription. |
| `transcribe` | Transcribes audio locally with `mlx-whisper`. |
| `chunk-transcripts` | Splits transcript JSON into overlapping chunk files. |
| `extract-knowledge` | Uses OpenAI to extract topics, terms, practices, and article candidates. |
| `build-topic-index` | Builds deterministic indexes from extracted knowledge. |
| `build-article-plan` | Selects article pages and source packs. |
| `draft-articles` | Uses OpenAI to draft wiki article Markdown. |
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
media-to-wiki-convertor draft-articles
media-to-wiki-convertor build-vault
```

## Cost And Privacy

Transcription is local. Your media and audio do not need to leave your machine for the transcription stage.

These stages send transcript-derived text to OpenAI:

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
- `Index/`
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
72 passed
```

## Notes

The default transcription engine is optimized for Apple Silicon via `mlx-whisper`. Other engines can be added later behind the same file-based pipeline.
