# Video KB CLI Design

## Goal

Turn the current local training pipeline into a reusable GitHub-ready CLI package named `video-kb`, with Python package name `video_kb`.

The product should let a user turn a local folder of videos into an Obsidian vault through a resumable, file-based pipeline:

1. discover videos
2. extract audio
3. validate audio
4. transcribe
5. chunk transcripts
6. extract structured knowledge
7. build a topic index
8. build an article plan
9. draft wiki articles
10. build an Obsidian vault

The first public version is a CLI app, not a web app and not a desktop GUI.

## Users

The intended user is a technical person who has local videos and wants a searchable Obsidian knowledge base without manually operating every pipeline step.

The user should be able to:

- initialize a new project folder;
- configure video, raw data, and vault paths;
- run the full pipeline;
- resume after interruption;
- rerun individual stages;
- inspect status and logs;
- keep secrets out of git;
- publish the project code to GitHub without committing generated data.

## CLI Name

Public command:

```bash
video-kb
```

Python package:

```text
video_kb
```

The current package `larchenko_kb` will be migrated to `video_kb` after the generic project behavior is in place.

## Project Model

A `video-kb` project is a normal folder containing:

```text
my-training/
  config.toml
  .env
  .env.example
  .gitignore
  raw-data/
  vault/
```

The CLI reads `config.toml` from the current working directory by default.

All generated heavy artifacts stay out of git:

- `raw-data/`
- `vault/`
- `.env`
- local model caches
- logs, unless the user explicitly chooses to keep them

The Obsidian vault may optionally be its own git repository. The root project should ignore the vault by default.

## Configuration

`config.toml` should be the durable source of project settings:

```toml
[paths]
video_source = "/path/to/videos"
raw_data = "./raw-data"
vault = "./vault"

[discover]
video_extensions = [".mp4", ".mov", ".mkv"]
max_depth = 8

[transcription]
engine = "mlx-whisper"
model = "mlx-community/whisper-medium"
language = "ru"

[llm]
provider = "openai"
model = "gpt-5.4-mini"

[chunking]
chunk_minutes = 10
overlap_seconds = 120
```

`.env` stores secrets:

```text
OPENAI_API_KEY=sk-proj-...
```

The CLI must never print API keys.

## Commands

### Initialize

```bash
video-kb init my-training
```

Creates:

- `config.toml`
- `.env.example`
- `.gitignore`
- `raw-data/`
- `vault/`
- a short local README

It must not overwrite existing non-empty files unless the user passes an explicit force flag.

### Configure

```bash
video-kb config \
  --videos "/path/to/videos" \
  --raw "./raw-data" \
  --vault "./vault" \
  --language ru
```

Updates `config.toml` without touching generated artifacts.

### Status

```bash
video-kb status
```

Shows:

- configured paths;
- number of videos;
- number of audio files;
- number of transcripts;
- number of chunks;
- number of extracted knowledge files;
- number of topic pages;
- number of article plan pages;
- number of drafted articles;
- vault output counts.

### Full Pipeline

```bash
video-kb run
```

Runs all stages in order. It should resume by default and skip completed outputs.

Options:

```bash
video-kb run --from transcribe
video-kb run --to build-vault
video-kb run --dry-run
video-kb run --yes
```

Before expensive LLM stages, the CLI should print a cost/control warning and ask for confirmation unless `--yes` is provided.

### Individual Stages

The existing stage commands remain available:

```bash
video-kb discover
video-kb import-list --file videos.txt --base "/path/to/videos"
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

Aliases can exist, but documentation should use one canonical command per stage.

## Pipeline State

The first public version should remain file-based and resumable:

- manifest: `raw-data/manifest/videos.jsonl`
- audio: `raw-data/audio/*.wav`
- transcripts: `raw-data/transcripts/*.{json,txt,srt}`
- chunks: `raw-data/chunks/<video_id>/<chunk_id>.json`
- extracted knowledge: `raw-data/extracted-knowledge/...`
- topic index: `raw-data/topic-index/`
- article plan: `raw-data/article-plan/`
- draft articles: `raw-data/draft-articles/`
- vault: configured `vault/`

SQLite is not required for the first GitHub-ready CLI. It can be added later if we build a UI or need richer job history.

## Obsidian Vault Output

The generated vault should contain:

```text
00 Home.md
Index/
Wiki/
Sources/
90 Transcripts.md
90 Transcripts/
```

Required links:

- Home links to main indexes.
- Wiki articles link to transcript notes and source chunks.
- Source chunks link to full transcript notes.
- Transcript notes link back to source chunks when used.
- All generated wikilinks must resolve.

Unknown generated links should not become broken Obsidian links. They should become plain text and be listed in `Index/Unlinked Mentions.md`.

## Error Handling

The CLI should fail early and clearly for:

- missing config;
- missing video folder;
- missing ffmpeg;
- invalid audio files;
- missing API key;
- placeholder API key;
- invalid OpenAI request;
- missing stage inputs.

Long-running stages should print progress with:

- current item index;
- video or chunk id;
- elapsed time per item;
- output file path;
- skip/fail status.

## Cost Control

LLM stages must support:

- `--dry-run`;
- `--limit`;
- `--sample-per-video`;
- `--force`;
- model override;
- explicit warning before full-corpus runs.

The default behavior should prefer skipping completed artifacts over recomputing.

## Packaging

`pyproject.toml` should define:

```toml
[project]
name = "video-kb"

[project.scripts]
video-kb = "video_kb.cli:main"

[project.optional-dependencies]
mlx = ["mlx-whisper"]
dev = ["pytest", "ruff"]
```

Core dependencies should stay small. Heavy or platform-specific dependencies should be optional.

## GitHub Readiness

Before publishing:

- rename package from `larchenko_kb` to `video_kb`;
- update imports and tests;
- update README with generic quickstart;
- add LICENSE;
- add `.github/workflows/test.yml`;
- ensure `.env`, generated raw data, and vault output are ignored;
- remove user-specific paths from committed config;
- keep `config.example.toml` and `.env.example`;
- run tests from a clean clone-style checkout.

## Migration Plan

Do this in small, safe commits:

1. Add generic config defaults while preserving the current project.
2. Add `init` and `config` commands.
3. Add `run` orchestration command.
4. Update README for the generic CLI.
5. Rename package and command from `larchenko_kb` to `video_kb` / `video-kb`.
6. Add GitHub workflow and packaging polish.

This order keeps the working pipeline usable throughout the migration.

## Out Of Scope For First Version

- Web UI.
- Desktop app wrapper.
- Multi-user server.
- Cloud upload.
- Hosted transcription.
- Database-backed job scheduler.
- Automatic GitHub publishing.

These can be added later after the CLI is stable.
