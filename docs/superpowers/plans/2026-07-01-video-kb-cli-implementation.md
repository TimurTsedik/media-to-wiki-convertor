# Video KB CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the current local `larchenko_kb` pipeline into a GitHub-ready generic CLI named `video-kb`.

**Architecture:** Keep the existing pipeline modules and add a thin generic project layer first. The CLI will read project-local `config.toml`, create reusable project scaffolds, orchestrate existing stages, and only then rename the package from `larchenko_kb` to `video_kb`.

**Tech Stack:** Python 3.11+, stdlib `argparse`, `pathlib`, `tomllib`, `tomli_w`, existing file-based pipeline, optional `mlx-whisper`, OpenAI via current stdlib HTTP client, Obsidian Markdown output.

---

## File Structure

Create:

- `larchenko_kb/project.py` - project scaffolding templates and `init`/`config` helpers while the package is still named `larchenko_kb`.
- `larchenko_kb/run_pipeline.py` - ordered stage runner for `video-kb run`.
- `tests/test_project.py` - tests for project init/config behavior.
- `tests/test_run_pipeline.py` - tests for full-pipeline orchestration without running heavy stages.
- `.github/workflows/test.yml` - GitHub Actions test workflow.
- `LICENSE` - MIT license.

Modify:

- `larchenko_kb/config.py` - load config from the current project directory instead of the package directory by default.
- `larchenko_kb/cli.py` - add `init`, `config`, and `run`; expose generic help text.
- `pyproject.toml` - rename public project metadata, add optional dependencies, expose `video-kb`.
- `README.md` - replace Larchenko-specific docs with generic quickstart and pipeline docs.
- `.gitignore` - ensure generic generated outputs are ignored.
- `.env.example` - keep safe secret template.
- `config.example.toml` - make generic paths and include chunking/provider settings.
- `tests/test_config.py` - cover project-local config resolution.
- Existing tests importing `larchenko_kb` - update only in the rename task.

Final rename task:

- Move `larchenko_kb/` to `video_kb/`.
- Update imports in package and tests.
- Update `python -m` examples from `larchenko_kb` to `video_kb`.

## Task 1: Make Config Project-Local

**Files:**
- Modify: `larchenko_kb/config.py`
- Modify: `tests/test_config.py`
- Modify: `config.example.toml`

- [ ] **Step 1: Write the failing tests**

Add these tests to `tests/test_config.py`:

```python
def test_load_config_defaults_to_current_project_config(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[paths]
video_source = "./videos"
raw_data = "./raw-data"
vault = "./vault"

[llm]
provider = "openai"
model = "gpt-5.4-mini"

[chunking]
chunk_minutes = 12
overlap_seconds = 90
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    config = load_config()

    assert config.paths.video_source == tmp_path / "videos"
    assert config.paths.raw_data == tmp_path / "raw-data"
    assert config.paths.vault == tmp_path / "vault"
    assert config.llm.provider == "openai"
    assert config.llm.model == "gpt-5.4-mini"
    assert config.chunking.chunk_minutes == 12
    assert config.chunking.overlap_seconds == 90


def test_load_config_expands_absolute_paths_without_rebasing(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[paths]
video_source = "/videos"
raw_data = "/raw"
vault = "/vault"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.paths.video_source == Path("/videos")
    assert config.paths.raw_data == Path("/raw")
    assert config.paths.vault == Path("/vault")
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import tests.test_config as t

for test in [
    t.test_load_config_defaults_to_current_project_config,
    t.test_load_config_expands_absolute_paths_without_rebasing,
]:
    with TemporaryDirectory() as tmp:
        try:
            test(Path(tmp))
        except TypeError:
            class MonkeyPatch:
                def chdir(self, path):
                    self.old = Path.cwd()
                    os.chdir(path)
            mp = MonkeyPatch()
            test(Path(tmp), mp)
print("config project-local tests: OK")
PY
```

Expected: fails because `load_config()` currently resolves defaults from the package root and `LLMConfig` has no `provider`; `PipelineConfig` has no `chunking`.

- [ ] **Step 3: Implement project-local config**

Update `larchenko_kb/config.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_NAME = "config.toml"
EXAMPLE_CONFIG_PATH = PACKAGE_ROOT / "config.example.toml"
DOTENV_NAME = ".env"


@dataclass(frozen=True)
class PipelinePaths:
    video_source: Path
    raw_data: Path
    vault: Path


@dataclass(frozen=True)
class DiscoverConfig:
    video_extensions: tuple[str, ...]
    max_depth: int


@dataclass(frozen=True)
class TranscriptionConfig:
    engine: str
    model: str
    language: str


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str


@dataclass(frozen=True)
class ChunkingConfig:
    chunk_minutes: int
    overlap_seconds: int


@dataclass(frozen=True)
class PipelineConfig:
    paths: PipelinePaths
    discover: DiscoverConfig
    transcription: TranscriptionConfig
    llm: LLMConfig
    chunking: ChunkingConfig


def load_config(config_path: Path | None = None) -> PipelineConfig:
    path = resolve_config_path(config_path)
    load_dotenv(path.parent / DOTENV_NAME)

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    paths = data["paths"]
    discover = data.get("discover", {})
    transcription = data.get("transcription", {})
    llm = data.get("llm", {})
    chunking = data.get("chunking", {})

    base_dir = path.parent
    return PipelineConfig(
        paths=PipelinePaths(
            video_source=resolve_project_path(base_dir, paths["video_source"]),
            raw_data=resolve_project_path(base_dir, paths["raw_data"]),
            vault=resolve_project_path(base_dir, paths["vault"]),
        ),
        discover=DiscoverConfig(
            video_extensions=tuple(
                ext.lower() for ext in discover.get("video_extensions", [".mp4", ".mov", ".mkv"])
            ),
            max_depth=int(discover.get("max_depth", 8)),
        ),
        transcription=TranscriptionConfig(
            engine=str(transcription.get("engine", "mlx-whisper")),
            model=str(transcription.get("model", "mlx-community/whisper-medium")),
            language=str(transcription.get("language", "ru")),
        ),
        llm=LLMConfig(
            provider=str(llm.get("provider", "openai")),
            model=str(llm.get("model", "gpt-5.4-mini")),
        ),
        chunking=ChunkingConfig(
            chunk_minutes=int(chunking.get("chunk_minutes", 10)),
            overlap_seconds=int(chunking.get("overlap_seconds", 120)),
        ),
    )


def resolve_config_path(config_path: Path | None = None) -> Path:
    if config_path is not None:
        return config_path.expanduser().resolve()

    cwd_config = Path.cwd() / DEFAULT_CONFIG_NAME
    if cwd_config.exists():
        return cwd_config
    return EXAMPLE_CONFIG_PATH


def resolve_project_path(base_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()
```

Keep the existing `load_dotenv()` and `clean_dotenv_value()` functions below this block.

Update `config.example.toml`:

```toml
[paths]
video_source = "./videos"
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

- [ ] **Step 4: Run the tests to verify GREEN**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
import inspect
import tests.test_config as t

for name, fn in sorted(vars(t).items()):
    if name.startswith("test_") and callable(fn):
        sig = inspect.signature(fn)
        with TemporaryDirectory() as tmp:
            if "tmp_path" in sig.parameters and "monkeypatch" in sig.parameters:
                class MonkeyPatch:
                    def __init__(self):
                        self.old = Path.cwd()
                    def chdir(self, path):
                        import os
                        os.chdir(path)
                    def undo(self):
                        import os
                        os.chdir(self.old)
                mp = MonkeyPatch()
                try:
                    fn(Path(tmp), mp)
                finally:
                    mp.undo()
            elif "tmp_path" in sig.parameters:
                fn(Path(tmp))
            else:
                fn()
print("test_config: OK")
PY
```

Expected: `test_config: OK`.

- [ ] **Step 5: Commit**

```bash
git add larchenko_kb/config.py tests/test_config.py config.example.toml
git commit -m "feat: load project-local config"
```

## Task 2: Add Project Initialization And Config Commands

**Files:**
- Create: `larchenko_kb/project.py`
- Create: `tests/test_project.py`
- Modify: `larchenko_kb/cli.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_project.py`:

```python
from pathlib import Path

from larchenko_kb.project import ProjectSettings, init_project, update_project_config


def test_init_project_creates_generic_project_layout(tmp_path: Path) -> None:
    target = tmp_path / "my-training"

    result = init_project(target)

    assert result.project_dir == target
    assert (target / "config.toml").exists()
    assert (target / ".env.example").exists()
    assert (target / ".gitignore").exists()
    assert (target / "raw-data").is_dir()
    assert (target / "vault").is_dir()
    assert (target / "README.local.md").exists()
    assert "OPENAI_API_KEY=" in (target / ".env.example").read_text(encoding="utf-8")
    assert "raw-data/" in (target / ".gitignore").read_text(encoding="utf-8")
    assert "vault/" in (target / ".gitignore").read_text(encoding="utf-8")


def test_init_project_refuses_to_overwrite_existing_config(tmp_path: Path) -> None:
    target = tmp_path / "my-training"
    target.mkdir()
    (target / "config.toml").write_text("existing", encoding="utf-8")

    try:
        init_project(target)
    except FileExistsError as exc:
        assert "config.toml" in str(exc)
    else:
        raise AssertionError("init_project overwrote an existing config.toml")


def test_update_project_config_changes_only_requested_values(tmp_path: Path) -> None:
    target = tmp_path / "my-training"
    init_project(target)

    update_project_config(
        target / "config.toml",
        ProjectSettings(
            videos=Path("/videos"),
            raw=Path("./data"),
            vault=Path("./notes"),
            language="en",
        ),
    )

    text = (target / "config.toml").read_text(encoding="utf-8")
    assert 'video_source = "/videos"' in text
    assert 'raw_data = "./data"' in text
    assert 'vault = "./notes"' in text
    assert 'language = "en"' in text
    assert 'model = "mlx-community/whisper-medium"' in text
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
import tests.test_project as t

for test in [
    t.test_init_project_creates_generic_project_layout,
    t.test_init_project_refuses_to_overwrite_existing_config,
    t.test_update_project_config_changes_only_requested_values,
]:
    with TemporaryDirectory() as tmp:
        test(Path(tmp))
print("test_project: OK")
PY
```

Expected: fails with `ModuleNotFoundError: No module named 'larchenko_kb.project'`.

- [ ] **Step 3: Implement `larchenko_kb/project.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG = """[paths]
video_source = "./videos"
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
"""

DEFAULT_ENV_EXAMPLE = """# Copy this file to .env and paste your real key.
OPENAI_API_KEY=
"""

DEFAULT_GITIGNORE = """.env
.venv/
__pycache__/
.DS_Store
raw-data/
vault/
"""

DEFAULT_LOCAL_README = """# Local Video KB Project

Run:

```bash
video-kb status
video-kb run
```

Generated files live in `raw-data/` and `vault/`.
"""


@dataclass(frozen=True)
class ProjectInitResult:
    project_dir: Path


@dataclass(frozen=True)
class ProjectSettings:
    videos: Path | None = None
    raw: Path | None = None
    vault: Path | None = None
    language: str | None = None


def init_project(project_dir: Path, force: bool = False) -> ProjectInitResult:
    project_dir = project_dir.expanduser()
    project_dir.mkdir(parents=True, exist_ok=True)

    write_new_file(project_dir / "config.toml", DEFAULT_CONFIG, force)
    write_new_file(project_dir / ".env.example", DEFAULT_ENV_EXAMPLE, force)
    write_new_file(project_dir / ".gitignore", DEFAULT_GITIGNORE, force)
    write_new_file(project_dir / "README.local.md", DEFAULT_LOCAL_README, force)
    (project_dir / "raw-data").mkdir(exist_ok=True)
    (project_dir / "vault").mkdir(exist_ok=True)
    return ProjectInitResult(project_dir=project_dir)


def write_new_file(path: Path, text: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8").strip() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.write_text(text, encoding="utf-8")


def update_project_config(config_path: Path, settings: ProjectSettings) -> None:
    text = config_path.read_text(encoding="utf-8")
    replacements: dict[str, str] = {}
    if settings.videos is not None:
        replacements["video_source"] = path_value(settings.videos)
    if settings.raw is not None:
        replacements["raw_data"] = path_value(settings.raw)
    if settings.vault is not None:
        replacements["vault"] = path_value(settings.vault)
    if settings.language is not None:
        replacements["language"] = settings.language

    for key, value in replacements.items():
        text = replace_toml_string(text, key, value)
    config_path.write_text(text, encoding="utf-8")


def path_value(path: Path) -> str:
    return str(path)


def replace_toml_string(text: str, key: str, value: str) -> str:
    lines = []
    replaced = False
    prefix = f"{key} = "
    for line in text.splitlines():
        if line.startswith(prefix):
            lines.append(f'{key} = "{value}"')
            replaced = True
        else:
            lines.append(line)
    if not replaced:
        lines.append(f'{key} = "{value}"')
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Wire CLI commands**

Modify `larchenko_kb/cli.py` imports:

```python
from larchenko_kb.project import ProjectSettings, init_project, update_project_config
```

Add parsers in `build_parser()`:

```python
    init_parser = subparsers.add_parser("init", help="Create a new video-kb project folder.")
    init_parser.add_argument("project_dir", type=Path)
    init_parser.add_argument("--force", action="store_true")

    config_parser = subparsers.add_parser("config", help="Update config.toml project settings.")
    config_parser.add_argument("--videos", type=Path, default=None)
    config_parser.add_argument("--raw", type=Path, default=None)
    config_parser.add_argument("--vault", type=Path, default=None)
    config_parser.add_argument("--language", default=None)
```

Handle commands before `load_config()` in `main()`:

```python
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "init":
        try:
            result = init_project(args.project_dir, force=args.force)
        except FileExistsError as exc:
            say(str(exc))
            return 1
        say(f"Created video-kb project: {result.project_dir}")
        return 0

    if args.command == "config":
        update_project_config(
            Path("config.toml"),
            ProjectSettings(
                videos=args.videos,
                raw=args.raw,
                vault=args.vault,
                language=args.language,
            ),
        )
        say("Updated config.toml")
        return 0

    config = load_config(args.config)
```

- [ ] **Step 5: Run tests to verify GREEN**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
import tests.test_project as t

for test in [
    t.test_init_project_creates_generic_project_layout,
    t.test_init_project_refuses_to_overwrite_existing_config,
    t.test_update_project_config_changes_only_requested_values,
]:
    with TemporaryDirectory() as tmp:
        test(Path(tmp))
print("test_project: OK")
PY
```

Expected: `test_project: OK`.

- [ ] **Step 6: Manually smoke test CLI**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
tmpdir="$(mktemp -d)"
.venv/bin/python -B -m larchenko_kb init "$tmpdir/demo"
cd "$tmpdir/demo"
"/Users/timur555/Documents/PycharmProjects/Other/larchenko training/.venv/bin/python" -B -m larchenko_kb config --videos "/videos" --raw "./data" --vault "./notes" --language en
test -f config.toml
test -d raw-data
test -d vault
```

Expected: no output from the `test` commands; init/config print success messages.

- [ ] **Step 7: Commit**

```bash
git add larchenko_kb/project.py larchenko_kb/cli.py tests/test_project.py
git commit -m "feat: add generic project init"
```

## Task 3: Add Full Pipeline Runner

**Files:**
- Create: `larchenko_kb/run_pipeline.py`
- Create: `tests/test_run_pipeline.py`
- Modify: `larchenko_kb/cli.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_run_pipeline.py`:

```python
from larchenko_kb.run_pipeline import STAGE_NAMES, select_stages


def test_select_stages_returns_full_pipeline_by_default() -> None:
    assert select_stages() == STAGE_NAMES


def test_select_stages_can_start_from_stage() -> None:
    assert select_stages(from_stage="transcribe") == STAGE_NAMES[STAGE_NAMES.index("transcribe") :]


def test_select_stages_can_stop_at_stage() -> None:
    assert select_stages(to_stage="chunk-transcripts") == STAGE_NAMES[: STAGE_NAMES.index("chunk-transcripts") + 1]


def test_select_stages_rejects_unknown_stage() -> None:
    try:
        select_stages(from_stage="unknown")
    except ValueError as exc:
        assert "Unknown stage" in str(exc)
    else:
        raise AssertionError("unknown stage was accepted")
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B - <<'PY'
import tests.test_run_pipeline as t

for test in [
    t.test_select_stages_returns_full_pipeline_by_default,
    t.test_select_stages_can_start_from_stage,
    t.test_select_stages_can_stop_at_stage,
    t.test_select_stages_rejects_unknown_stage,
]:
    test()
print("test_run_pipeline: OK")
PY
```

Expected: fails with `ModuleNotFoundError: No module named 'larchenko_kb.run_pipeline'`.

- [ ] **Step 3: Implement `run_pipeline.py`**

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from larchenko_kb.config import PipelineConfig


STAGE_NAMES = [
    "discover",
    "extract-audio",
    "validate-audio",
    "transcribe",
    "chunk-transcripts",
    "extract-knowledge",
    "build-topic-index",
    "build-article-plan",
    "draft-articles",
    "build-vault",
]


@dataclass(frozen=True)
class PipelineStage:
    name: str
    run: Callable[[PipelineConfig], int]
    expensive: bool = False


def select_stages(from_stage: str | None = None, to_stage: str | None = None) -> list[str]:
    start = stage_index(from_stage) if from_stage else 0
    end = stage_index(to_stage) + 1 if to_stage else len(STAGE_NAMES)
    if start >= end:
        raise ValueError("--from must come before or equal --to")
    return STAGE_NAMES[start:end]


def stage_index(stage: str) -> int:
    if stage not in STAGE_NAMES:
        raise ValueError(f"Unknown stage: {stage}. Known stages: {', '.join(STAGE_NAMES)}")
    return STAGE_NAMES.index(stage)


def run_selected_stages(
    config: PipelineConfig,
    stages: dict[str, PipelineStage],
    from_stage: str | None = None,
    to_stage: str | None = None,
    assume_yes: bool = False,
    dry_run: bool = False,
    say: Callable[[str], None] = print,
) -> int:
    selected = select_stages(from_stage=from_stage, to_stage=to_stage)
    if dry_run:
        say("Pipeline dry run:")
        for name in selected:
            say(f"- {name}")
        return 0

    for name in selected:
        stage = stages[name]
        if stage.expensive and not assume_yes:
            say(f"Stage {name} may call paid LLM APIs. Re-run with --yes to continue.")
            return 1
        say(f"Run stage: {name}")
        code = stage.run(config)
        if code:
            say(f"Stage failed: {name}")
            return code
    say("Pipeline complete.")
    return 0
```

- [ ] **Step 4: Wire CLI `run` command**

In `larchenko_kb/cli.py`, import:

```python
from larchenko_kb.run_pipeline import PipelineStage, run_selected_stages
```

Add parser:

```python
    run_parser = subparsers.add_parser("run", help="Run the full pipeline in order.")
    run_parser.add_argument("--from", dest="from_stage", default=None)
    run_parser.add_argument("--to", dest="to_stage", default=None)
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--yes", action="store_true")
```

Add helper:

```python
def pipeline_stages() -> dict[str, PipelineStage]:
    return {
        "discover": PipelineStage("discover", lambda config: discover(config)),
        "extract-audio": PipelineStage("extract-audio", lambda config: extract_audio(config)),
        "validate-audio": PipelineStage("validate-audio", lambda config: validate_audio(config)),
        "transcribe": PipelineStage("transcribe", lambda config: transcribe(config)),
        "chunk-transcripts": PipelineStage(
            "chunk-transcripts",
            lambda config: chunk_transcripts(
                config,
                config.chunking.chunk_minutes,
                config.chunking.overlap_seconds,
            ),
        ),
        "extract-knowledge": PipelineStage(
            "extract-knowledge",
            lambda config: extract_knowledge(config, None, None, None, False, False),
            expensive=True,
        ),
        "build-topic-index": PipelineStage("build-topic-index", lambda config: build_topic_index(config)),
        "build-article-plan": PipelineStage(
            "build-article-plan",
            lambda config: build_article_plan(config, min_sources=2, max_pages=None),
        ),
        "draft-articles": PipelineStage(
            "draft-articles",
            lambda config: draft_articles(config, None, None, False, False),
            expensive=True,
        ),
        "build-vault": PipelineStage("build-vault", lambda config: build_vault(config)),
    }
```

Handle command:

```python
    if args.command == "run":
        return run_selected_stages(
            config,
            pipeline_stages(),
            from_stage=args.from_stage,
            to_stage=args.to_stage,
            assume_yes=args.yes,
            dry_run=args.dry_run,
            say=say,
        )
```

- [ ] **Step 5: Run tests to verify GREEN**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B - <<'PY'
import tests.test_run_pipeline as t

for test in [
    t.test_select_stages_returns_full_pipeline_by_default,
    t.test_select_stages_can_start_from_stage,
    t.test_select_stages_can_stop_at_stage,
    t.test_select_stages_rejects_unknown_stage,
]:
    test()
print("test_run_pipeline: OK")
PY
```

Expected: `test_run_pipeline: OK`.

- [ ] **Step 6: Smoke test dry run**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
.venv/bin/python -B -m larchenko_kb run --dry-run --from chunk-transcripts --to build-vault
```

Expected output includes:

```text
Pipeline dry run:
- chunk-transcripts
- extract-knowledge
- build-topic-index
- build-article-plan
- draft-articles
- build-vault
```

- [ ] **Step 7: Commit**

```bash
git add larchenko_kb/run_pipeline.py larchenko_kb/cli.py tests/test_run_pipeline.py
git commit -m "feat: add resumable pipeline runner"
```

## Task 4: Update GitHub Packaging Metadata And Docs

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `.gitignore`
- Modify: `.env.example`
- Create: `LICENSE`
- Create: `.github/workflows/test.yml`

- [ ] **Step 1: Write metadata checks**

Create a temporary manual check command for this task:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B - <<'PY'
from pathlib import Path
import tomllib

data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
assert data["project"]["name"] == "video-kb"
assert data["project"]["scripts"]["video-kb"] == "larchenko_kb.cli:main"
assert "mlx" in data["project"]["optional-dependencies"]
assert "dev" in data["project"]["optional-dependencies"]
readme = Path("README.md").read_text(encoding="utf-8")
assert "video-kb init" in readme
assert "video-kb run" in readme
assert "OPENAI_API_KEY" in readme
assert Path("LICENSE").exists()
assert Path(".github/workflows/test.yml").exists()
print("packaging docs check: OK")
PY
```

Expected before edits: fails because metadata still says `larchenko-kb`.

- [ ] **Step 2: Update `pyproject.toml`**

Set:

```toml
[project]
name = "video-kb"
version = "0.1.0"
description = "Local CLI for turning video folders into Obsidian knowledge bases."
requires-python = ">=3.11"
dependencies = ["numpy"]

[project.optional-dependencies]
mlx = ["mlx-whisper"]
dev = ["pytest", "ruff"]

[project.scripts]
video-kb = "larchenko_kb.cli:main"
larchenko-kb = "larchenko_kb.cli:main"
```

Keep the temporary `larchenko-kb` script until the final rename task is complete.

- [ ] **Step 3: Replace README with generic quickstart**

Use this structure in `README.md`:

```markdown
# video-kb

`video-kb` is a local CLI that turns a folder of videos into an Obsidian knowledge base.

## What It Does

1. discovers videos
2. extracts audio with ffmpeg
3. transcribes locally with mlx-whisper
4. chunks transcripts with overlap
5. extracts structured knowledge with OpenAI
6. drafts wiki articles
7. builds an Obsidian vault with links to sources and transcripts

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
video-kb config --videos "/path/to/videos" --raw "./raw-data" --vault "./vault" --language ru
video-kb status
video-kb run --dry-run
video-kb run --yes
```

## Cost Warning

The transcription stage is local. The `extract-knowledge` and `draft-articles` stages call OpenAI APIs and may cost money. Use `--dry-run`, `--limit`, and `--sample-per-video` before full runs.

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
```

- [ ] **Step 4: Update `.gitignore`**

Ensure it contains:

```gitignore
.env
.venv/
__pycache__/
.DS_Store
raw data/
raw-data/
larchenko_training_vault/
vault/
config.toml
```

- [ ] **Step 5: Update `.env.example`**

Use:

```text
# Copy this file to .env and paste your real key.
OPENAI_API_KEY=
```

- [ ] **Step 6: Add MIT license**

Create `LICENSE`:

```text
MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 7: Add GitHub Actions workflow**

Create `.github/workflows/test.yml`:

```yaml
name: tests

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install --upgrade pip
      - run: python -m pip install -e '.[dev]'
      - run: pytest
```

- [ ] **Step 8: Run metadata check**

Run the command from Step 1.

Expected: `packaging docs check: OK`.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml README.md .gitignore .env.example LICENSE .github/workflows/test.yml
git commit -m "docs: prepare generic cli package"
```

## Task 5: Rename Package To `video_kb`

**Files:**
- Move: `larchenko_kb/` to `video_kb/`
- Modify: all Python imports in `video_kb/*.py`
- Modify: all tests importing `larchenko_kb`
- Modify: `pyproject.toml`
- Modify: README command examples that use `python -m larchenko_kb`

- [ ] **Step 1: Rename package directory**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
git mv larchenko_kb video_kb
```

- [ ] **Step 2: Rewrite imports**

Run a controlled replacement:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
python3 - <<'PY'
from pathlib import Path

for root in [Path("video_kb"), Path("tests")]:
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        text = text.replace("larchenko_kb", "video_kb")
        path.write_text(text, encoding="utf-8")
PY
```

- [ ] **Step 3: Update `pyproject.toml`**

Set scripts and package include:

```toml
[project.scripts]
video-kb = "video_kb.cli:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["video_kb*"]
```

Remove the temporary `larchenko-kb` script.

- [ ] **Step 4: Update `video_kb/__main__.py`**

Ensure it imports:

```python
from video_kb.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run import smoke tests**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B - <<'PY'
import video_kb
from video_kb.cli import main
from video_kb.config import load_config
print("video_kb imports: OK")
PY
```

Expected: `video_kb imports: OK`.

- [ ] **Step 6: Run full manual test suite**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
import inspect

modules = [
    "tests.test_config",
    "tests.test_manifest",
    "tests.test_audio",
    "tests.test_transcription",
    "tests.test_chunks",
    "tests.test_knowledge",
    "tests.test_topic_index",
    "tests.test_article_plan",
    "tests.test_draft_articles",
    "tests.test_vault",
    "tests.test_project",
    "tests.test_run_pipeline",
]

for module_name in modules:
    module = __import__(module_name, fromlist=["*"])
    for name, fn in sorted(vars(module).items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        sig = inspect.signature(fn)
        if "tmp_path" in sig.parameters:
            with TemporaryDirectory() as tmp:
                if "monkeypatch" in sig.parameters:
                    class MonkeyPatch:
                        def __init__(self):
                            self.old = Path.cwd()
                        def chdir(self, path):
                            import os
                            os.chdir(path)
                        def undo(self):
                            import os
                            os.chdir(self.old)
                    mp = MonkeyPatch()
                    try:
                        fn(Path(tmp), mp)
                    finally:
                        mp.undo()
                else:
                    fn(Path(tmp))
        else:
            fn()
print("manual test suite: OK")
PY
```

Expected: `manual test suite: OK`.

- [ ] **Step 7: Run CLI smoke tests**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
.venv/bin/python -B -m video_kb --help
.venv/bin/python -B -m video_kb run --dry-run --from build-topic-index --to build-vault
```

Expected: help output for the CLI; dry run prints selected stages and does not call OpenAI.

- [ ] **Step 8: Commit**

```bash
git add video_kb tests pyproject.toml README.md
git add -u larchenko_kb
git commit -m "refactor: rename package to video_kb"
```

## Task 6: Final GitHub Readiness Check

**Files:**
- Modify only if checks reveal a concrete issue.

- [ ] **Step 1: Check for user-specific names and paths**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
rg -n "Larchenko|larchenko|ЛАРЧЕНКО|timur555|My Passport|PycharmProjects" README.md pyproject.toml config.example.toml .env.example video_kb tests docs/superpowers/specs docs/superpowers/plans
```

Expected: no matches except historical design/plan docs where paths appear in command examples. If README, package code, tests, or config examples match, replace them with generic paths.

- [ ] **Step 2: Check ignored generated files**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
git check-ignore -v .env raw-data/ vault/ "raw data/" larchenko_training_vault/
```

Expected: each path is ignored by `.gitignore`.

- [ ] **Step 3: Check install metadata**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B - <<'PY'
import tomllib
from pathlib import Path
data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
assert data["project"]["name"] == "video-kb"
assert data["project"]["scripts"]["video-kb"] == "video_kb.cli:main"
assert data["tool"]["setuptools"]["packages"]["find"]["include"] == ["video_kb*"]
print("metadata: OK")
PY
```

Expected: `metadata: OK`.

- [ ] **Step 4: Run full verification**

Run:

```bash
cd "/Users/timur555/Documents/PycharmProjects/Other/larchenko training"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B - <<'PY'
from pathlib import Path
for path in [*Path("video_kb").glob("*.py"), *Path("tests").glob("test_*.py")]:
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("source compile check: OK")
PY
```

Expected: `source compile check: OK`.

If `pytest` is installed after Task 4:

```bash
.venv/bin/python -m pytest
```

Expected: all tests pass.

- [ ] **Step 5: Commit final fixes if any**

If Step 1-4 required edits:

```bash
git add README.md pyproject.toml config.example.toml .gitignore video_kb tests
git commit -m "chore: finish github-ready cli polish"
```

If no edits were required, do not create an empty commit.

## Self-Review

- Spec coverage: `init`, `config`, `run`, project-local config, cost warnings, docs, packaging, generated-output ignore rules, and package rename all have tasks.
- Scope: This plan stays CLI-only and does not include GUI, SQLite, cloud upload, or hosted transcription.
- Type consistency: `ProjectSettings`, `PipelineStage`, `PipelineConfig.chunking`, and `LLMConfig.provider` are defined before later tasks use them.
- Verification: Each implementation task has RED, GREEN, smoke checks, and a commit step.
