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

[wiki]
language = "ru"

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

DEFAULT_LOCAL_README = """# Local Media To Wiki Convertor Project

Run:

```bash
media-to-wiki-convertor status
media-to-wiki-convertor run
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
    text = str(path)
    if path.is_absolute() or text.startswith("."):
        return text
    return f"./{text}"


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
