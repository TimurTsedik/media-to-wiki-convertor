# video-kb

`video-kb` is a local CLI that turns a folder of videos into an Obsidian knowledge base.

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
video-kb init my-training
cd my-training
cp .env.example .env
# edit .env and set OPENAI_API_KEY before LLM stages
video-kb config --videos "/path/to/videos" --raw "./raw-data" --vault "./vault" --language ru
video-kb status
video-kb run --dry-run
video-kb run --yes
```

## Cost Warning

The transcription stage is local. The `extract-knowledge` and `draft-articles` stages call
OpenAI APIs and may cost money. Use `--dry-run`, `--limit`, and `--sample-per-video` before
full runs.

## Stage Commands

```bash
video-kb discover
video-kb extract-audio
video-kb validate-audio
video-kb transcribe
video-kb chunk-transcripts
video-kb extract-knowledge
video-kb build-topic-index
video-kb build-article-plan
video-kb draft-articles
video-kb build-vault
```

## Generated Output

Generated raw data and vault files should stay out of the root repository by default:

- `raw-data/`
- `vault/`
- `.env`
