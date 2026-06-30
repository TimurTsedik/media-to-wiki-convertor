# Larchenko KB Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small Python pipeline that turns read-only Russian training videos into raw transcripts and a separate Obsidian vault without wasting LLM tokens.

**Architecture:** The project keeps source videos read-only, generated artifacts under `raw data/`, and polished Markdown notes in `larchenko_training_vault/`. The CLI is stage-based and incremental: discovery first, then audio extraction, transcription, chunking, summarization, and vault generation.

**Tech Stack:** Python 3.11+, stdlib CLI/config/JSONL for the initial scaffold; later stages can add `ffmpeg`, local Whisper, and OpenAI-compatible LLM calls as optional dependencies.

---

### Task 1: Project Scaffold

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `config.example.toml`
- Create: `pyproject.toml`
- Create: `larchenko_kb/__init__.py`
- Create: `larchenko_kb/__main__.py`
- Create: `larchenko_kb/config.py`
- Create: `larchenko_kb/manifest.py`
- Create: `larchenko_kb/cli.py`
- Create: `tests/test_config.py`
- Create: `tests/test_manifest.py`

- [ ] Create the Python package and CLI.
- [ ] Add config loading from `config.toml` with fallback to `config.example.toml`.
- [ ] Add `status` and `discover` commands.
- [ ] Add unit tests for config and manifest behavior.
- [ ] Run `python3 -m pytest`.

### Task 2: Vault and Raw Data Layout

**Files:**
- Create: `larchenko_training_vault/.gitignore`
- Create: `larchenko_training_vault/00 Home/Larchenko Training Index.md`
- Create directories under `raw data/`

- [ ] Ignore `raw data/` and `larchenko_training_vault/` from the root repo.
- [ ] Initialize a separate git repository inside the vault.
- [ ] Add vault folders for home, videos, topics, concepts, quotes, and transcripts.
- [ ] Keep Obsidian workspace files out of the vault repo.

### Task 3: Next Stage

**Files:**
- Modify: `larchenko_kb/cli.py`
- Create: `larchenko_kb/audio.py`
- Create: `tests/test_audio.py`

- [ ] Add `extract-audio` using `ffmpeg`.
- [ ] Make extraction idempotent by checking output paths.
- [ ] Preserve video IDs from the manifest.
- [ ] Write logs under `raw data/logs/`.
