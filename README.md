# Larchenko Training Pipeline

Small Python pipeline for turning the Larchenko video training archive into a separate Obsidian knowledge base.

## Layout

```text
larchenko training/
  larchenko_kb/              # Python package and CLI
  tests/                     # Unit tests for the pipeline code
  raw data/                  # Generated audio, transcripts, chunks, logs
  larchenko_training_vault/  # Separate Obsidian vault with its own git repo
```

The source videos are read from:

```text
/Volumes/My Passport/ЛАРЧЕНКО/
```

The pipeline writes generated raw files to:

```text
/Users/timur555/Documents/PycharmProjects/Other/larchenko training/raw data/
```

The final Obsidian notes are written to:

```text
/Users/timur555/Documents/PycharmProjects/Other/larchenko training/larchenko_training_vault/
```

## First Commands

```bash
python3 -m larchenko_kb status
python3 -m larchenko_kb discover
python3 -m larchenko_kb status
```

`discover` creates `raw data/manifest/videos.jsonl`. It is safe to re-run.

If the external disk is slow to list, point discovery at a narrower subfolder:

```bash
python3 -m larchenko_kb discover --source "/Volumes/My Passport/ЛАРЧЕНКО/<subfolder>"
```

If Codex cannot list the external disk but your Terminal can, create a text list in Terminal and import it:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
ls -1 "/Volumes/My Passport/ЛАРЧЕНКО" > "raw data/manual_video_list.txt"
python3 -m larchenko_kb import-list \
  --file "raw data/manual_video_list.txt" \
  --base "/Volumes/My Passport/ЛАРЧЕНКО"
```

Audio extraction requires `ffmpeg` on `PATH`:

```bash
brew install ffmpeg
python3 -m larchenko_kb extract-audio
```

If Codex's terminal stalls on the external drive, run heavy disk/video commands from a fresh normal Terminal window. The pipeline state is file-based, so Codex can continue after Terminal finishes:

```bash
python3 -m larchenko_kb status
```

## Pipeline Stages

1. `discover` - scan the read-only video disk and build a manifest.
2. `extract-audio` - planned stage for `ffmpeg` extraction.
3. `transcribe` - planned stage for local Whisper transcription.
4. `chunk` - planned stage for transcript chunking with timestamps.
5. `summarize` - planned stage for low-token LLM summarization.
6. `build-vault` - planned stage for Obsidian Markdown generation.

The first implementation intentionally starts with `status` and `discover` so the project is testable before adding heavyweight audio and model dependencies.
