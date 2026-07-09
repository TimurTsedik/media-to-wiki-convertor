# media-to-wiki-convertor

`media-to-wiki-convertor` is a local CLI that turns a folder of videos into an Obsidian knowledge base.

## What It Does

1. Discovers videos.
2. Extracts audio with ffmpeg.
3. Transcribes locally with mlx-whisper.
4. Chunks transcripts with overlap.
5. Extracts structured knowledge with OpenAI.
6. Drafts wiki articles.
7. Builds an Obsidian vault with links to sources and transcripts.

## Requirements

- Python 3.11+
- ffmpeg
- macOS Apple Silicon for the default `mlx-whisper` transcription engine
- OpenAI API key for knowledge extraction and article drafting

## Install For Development

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[mlx,dev]'
```

## Quickstart

```bash
media-to-wiki-convertor init my-training
cd my-training
cp .env.example .env
# edit .env and set OPENAI_API_KEY before LLM stages
media-to-wiki-convertor config --videos "/path/to/videos" --raw "./raw-data" --vault "./vault" --language ru
media-to-wiki-convertor status
media-to-wiki-convertor run --dry-run
media-to-wiki-convertor run --yes
```

## Cost Warning

The transcription stage is local. The `extract-knowledge` and `draft-articles` stages call
OpenAI APIs and may cost money. Use `--dry-run`, `--limit`, and `--sample-per-video` before
full runs.

## Stage Commands

```bash
media-to-wiki-convertor discover
media-to-wiki-convertor extract-audio
media-to-wiki-convertor validate-audio
media-to-wiki-convertor transcribe
media-to-wiki-convertor chunk-transcripts
media-to-wiki-convertor extract-knowledge
media-to-wiki-convertor build-topic-index
media-to-wiki-convertor build-article-plan
media-to-wiki-convertor draft-articles
media-to-wiki-convertor build-vault
```

## Generated Output

Generated raw data and vault files should stay out of the root repository by default:

- `raw-data/`
- `vault/`
- `.env`
