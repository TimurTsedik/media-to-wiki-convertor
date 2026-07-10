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
- builds an Obsidian vault with linked articles, course materials, source chunks, and transcripts

## Why This Exists

Long recordings are full of useful knowledge, but raw transcripts are a swamp. This project turns the swamp into a map: articles, indexes, source notes, and transcript references that are easy to browse, search, and improve inside Obsidian.

## Pipeline

```text
videos
  -> audio
  -> transcripts
  -> overlapping chunks
  -> artifact healthcheck
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
- High-level catalog: planned articles and deferred topics are grouped into deterministic catalog pages.
- Course materials: the pipeline builds a course reference plan and drafts chapter-style notes from the catalog.
- Source-backed course chapters: generated chapter drafts are post-processed so source references become Obsidian links to `Sources/Chunks/...`.
- Linked section maps: `## Карта раздела` entries are normalized into links to wiki articles, chapter headings, or the chapter source appendix.
- Compact course prompts: `draft-course-materials` uses a small default source budget and exposes `--max-topics` / `--max-chunk-chars` for larger-context models.

## Real-World Validation

The current pipeline has been exercised end-to-end on a 32-video Russian-language training corpus of roughly 48 hours of material.

That run produced:

- 32 transcripts
- 353 overlapping transcript chunks
- 353 extracted knowledge files
- 1,543 topic pages before article planning
- 47 drafted wiki articles
- 102 catalog categories
- 102 drafted course material chapters
- an Obsidian vault with 9,340 wikilinks and 0 missing wikilinks

The generated vault includes wiki articles, source chunk notes, transcript notes, catalog indexes, and a `Course Materials/` section designed to read like course reference material rather than raw meeting notes.

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

`[transcription].language` is passed to the transcription engine. `[wiki].language` controls the language used for extracted knowledge, drafted articles, course materials, and generated wiki section headings.

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
| `healthcheck` | Validates resumable raw-data artifacts before continuing a run. |
| `extract-knowledge` | Uses the configured LLM provider to extract topics, terms, practices, and article candidates. |
| `build-topic-index` | Builds deterministic indexes from extracted knowledge. |
| `build-article-plan` | Selects article pages and source packs. Defaults to keeping single-source topics; use `--min-sources 2` for stricter filtering. |
| `build-catalog` | Groups planned articles and deferred topics into deterministic catalog categories with merge suggestions. |
| `build-course-plan` | Builds deterministic course reference chapters from catalog categories, existing articles, and deferred topics. |
| `draft-articles` | Uses the configured LLM provider to draft wiki article Markdown. |
| `draft-course-materials` | Uses the configured LLM provider to draft course reference chapter Markdown. |
| `build-vault` | Builds the final Obsidian vault. |

`draft-course-materials` uses a compact prompt budget by default so small-context models do not choke on large course chapters. Start with a small test batch:

```bash
media-to-wiki-convertor draft-course-materials --limit 3
```

If your model has a larger context window and you want richer chapter drafts, increase the source budget:

```bash
media-to-wiki-convertor draft-course-materials --limit 3 --max-topics 16 --max-chunk-chars 700
```

Example:

```bash
media-to-wiki-convertor discover
media-to-wiki-convertor extract-audio
media-to-wiki-convertor transcribe
media-to-wiki-convertor chunk-transcripts
media-to-wiki-convertor healthcheck
media-to-wiki-convertor extract-knowledge --sample-per-video 1
media-to-wiki-convertor build-topic-index
media-to-wiki-convertor build-article-plan
media-to-wiki-convertor build-catalog
media-to-wiki-convertor build-course-plan
media-to-wiki-convertor draft-articles
media-to-wiki-convertor draft-course-materials --limit 3
media-to-wiki-convertor build-vault
```

## Cost And Granularity Tuning

The expensive part is not Obsidian generation. The expensive part is sending transcript-derived text to an LLM.

The main cost drivers are:

- number of transcript chunks processed by `extract-knowledge`
- chunk size and overlap
- number of article drafts produced by `draft-articles`
- number and source budget of course material drafts produced by `draft-course-materials`
- model/provider choice in `[llm]`

### Cheap Trial Run

Use this when validating paths, language settings, prompts, and provider credentials:

```bash
media-to-wiki-convertor chunk-transcripts --chunk-minutes 10 --overlap-seconds 120
media-to-wiki-convertor extract-knowledge --sample-per-video 1
media-to-wiki-convertor build-topic-index
media-to-wiki-convertor build-article-plan --max-pages 5
media-to-wiki-convertor build-catalog
media-to-wiki-convertor build-course-plan
media-to-wiki-convertor draft-articles --limit 2
media-to-wiki-convertor draft-course-materials --limit 2 --max-topics 4 --max-chunk-chars 250
media-to-wiki-convertor build-vault
```

This samples only a small part of the corpus and drafts only a few pages. It is good for checking whether the output shape is useful before paying for the whole run.

### Balanced Run

This is the default shape for most training/course material:

```bash
media-to-wiki-convertor chunk-transcripts --chunk-minutes 10 --overlap-seconds 120
media-to-wiki-convertor extract-knowledge
media-to-wiki-convertor build-topic-index
media-to-wiki-convertor build-article-plan --min-sources 1
media-to-wiki-convertor build-catalog
media-to-wiki-convertor build-course-plan
media-to-wiki-convertor draft-articles
media-to-wiki-convertor draft-course-materials
media-to-wiki-convertor build-vault
```

`--min-sources 1` keeps rare but potentially useful topics as standalone articles. Use it when recall matters more than having a small, polished wiki.

### More Expensive / More Selective Run

Use this when you want fewer standalone articles, more evidence per article, and richer course chapters:

```bash
media-to-wiki-convertor chunk-transcripts --chunk-minutes 8 --overlap-seconds 180
media-to-wiki-convertor extract-knowledge
media-to-wiki-convertor build-topic-index
media-to-wiki-convertor build-article-plan --min-sources 2 --max-pages 80
media-to-wiki-convertor build-catalog
media-to-wiki-convertor build-course-plan
media-to-wiki-convertor draft-articles
media-to-wiki-convertor draft-course-materials --max-topics 16 --max-chunk-chars 700
media-to-wiki-convertor build-vault
```

Smaller chunks plus larger overlap usually improve source precision and topic recovery, but they create more chunks and therefore more `extract-knowledge` calls. Larger `--max-topics` and `--max-chunk-chars` give the course-materials LLM more context per chapter, but increase prompt size and cost.

### Cheaper / Coarser Run

Use this when you mainly need search and broad course chapters:

```bash
media-to-wiki-convertor chunk-transcripts --chunk-minutes 15 --overlap-seconds 60
media-to-wiki-convertor extract-knowledge
media-to-wiki-convertor build-topic-index
media-to-wiki-convertor build-article-plan --min-sources 2 --max-pages 40
media-to-wiki-convertor build-catalog
media-to-wiki-convertor build-course-plan
media-to-wiki-convertor draft-articles
media-to-wiki-convertor draft-course-materials --max-topics 6 --max-chunk-chars 250
media-to-wiki-convertor build-vault
```

This reduces standalone article count and keeps course prompts compact. The tradeoff is lower source precision and a higher chance that small but useful topics stay catalog-only.

### Article Granularity

Article granularity is controlled mostly by `build-article-plan`:

- `build-topic-index` reads extracted knowledge and builds candidate pages only from `wiki_candidates`.
- `build-article-plan` canonicalizes similar candidate titles into article groups.
- `--min-sources` decides how many distinct source chunks a candidate needs before it becomes a standalone article.
- `--max-pages` keeps only the top N article groups by deterministic score.

The current deterministic score is:

```text
source_count * 100 + mention_count * 10 + alias_count
```

That means a topic mentioned across many chunks outranks a topic that appears many times in only one chunk.

Practical settings:

- `--min-sources 1`: more articles, more long-tail topics, more cleanup later.
- `--min-sources 2`: fewer articles, better evidence, more material goes to `deferred`.
- `--max-pages 40`: compact wiki.
- `--max-pages 100`: broader wiki.
- no `--max-pages`: keep every article candidate that passes `--min-sources`.

### What Deferred Means

`deferred` does not mean deleted.

A topic goes to `raw-data/article_plan/deferred.json` when it was a wiki candidate but did not become a standalone article because:

- it had fewer source chunks than `--min-sources`
- or it ranked below `--max-pages`

Deferred topics are still used in later stages:

- `build-catalog` groups them into catalog categories.
- `build-catalog` writes merge suggestions to `raw-data/catalog/merge_suggestions.json`.
- `build-course-plan` turns catalog categories into Course Materials chapters.
- `draft-course-materials` can include deferred topics and their chunk text in chapter drafts.
- `build-vault` writes `Index/Deferred Topics.md`, catalog pages, source chunk links, and Course Materials appendices.

Deferred topics are not used for:

- standalone files under `Wiki/`
- `draft-articles`
- article source packs under `raw-data/article_plan/source_packs/`

This is intentional. Standalone wiki articles should be reasonably evidence-backed; deferred topics remain findable through catalog pages, Course Materials, source chunks, and the Deferred Topics index.

Some extracted items may not enter `deferred` at all. `topics`, `terms`, `practices`, `mistakes`, and `questions` are preserved inside extracted knowledge JSON and topic indexes, but only `wiki_candidates` are considered for standalone article planning.

### Merge Suggestions

`build-catalog` also writes `raw-data/catalog/merge_suggestions.json`.

Typical actions are:

- `merge_as_alias`: deferred topic title is effectively another name for an existing article.
- `merge_as_section`: deferred topic probably belongs as a section inside an existing article.
- `catalog_only`: keep it in catalog/course materials, but do not create an article yet.
- `needs_review`: usually uncategorized or weakly classified; inspect manually.

These suggestions are deterministic hints. The pipeline does not rewrite article plans automatically from them yet.

## Cost And Privacy

Transcription is local. Your media and audio do not need to leave your machine for the transcription stage.

These stages send transcript-derived text to the configured LLM provider:

- `extract-knowledge`
- `draft-articles`
- `draft-course-materials`

Use trial runs before sending everything:

```bash
media-to-wiki-convertor extract-knowledge --sample-per-video 1 --dry-run
media-to-wiki-convertor draft-articles --limit 1 --dry-run
media-to-wiki-convertor draft-course-materials --limit 1 --dry-run
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

`build-vault` treats these vault folders as generated output and rewrites them on every run:

- `Wiki/`
- `Index/`
- `Sources/`
- `90 Transcripts/`
- `Course Materials/`

Keep manual Obsidian notes outside those managed folders, or commit/back them up before rebuilding the vault.

The vault contains:

- `00 Home.md`
- `Course Materials/`
- `Index/`
- `Index/Catalog/`
- `Wiki/`
- `Sources/`
- `90 Transcripts.md`
- `90 Transcripts/`

Course material pages are post-processed during `build-vault`:

- source references such as `video_id:abc123#0004`, `[abc123#0004]`, `source://...`, and model-generated Markdown source links are normalized to `[[Sources/Chunks/abc123/0004|abc123/0004]]`
- known generated section headings are localized to `[wiki].language`, so English vaults do not keep Russian template headings such as `Карта раздела` or `Источники`
- unknown course-map entries are linked to a matching local chapter heading when possible
- remaining map entries link to the chapter's full source appendix instead of becoming dead text
- existing vault links are preserved

## Testing

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
.venv/bin/media-to-wiki-convertor --help
```

Expected result:

```text
136 passed
```

## Notes

The default transcription engine is optimized for Apple Silicon via `mlx-whisper`. Other engines can be added later behind the same file-based pipeline.
Users who already have transcripts can skip `extract-audio` and `transcribe` by importing transcript files directly.
