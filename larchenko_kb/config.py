from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.toml"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "config.example.toml"
DOTENV_PATH = PROJECT_ROOT / ".env"


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
    model: str


@dataclass(frozen=True)
class PipelineConfig:
    paths: PipelinePaths
    discover: DiscoverConfig
    transcription: TranscriptionConfig
    llm: LLMConfig


def load_config(config_path: Path | None = None) -> PipelineConfig:
    load_dotenv(DOTENV_PATH)

    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        path = EXAMPLE_CONFIG_PATH

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    paths = data["paths"]
    discover = data.get("discover", {})
    transcription = data.get("transcription", {})
    llm = data.get("llm", {})

    return PipelineConfig(
        paths=PipelinePaths(
            video_source=Path(paths["video_source"]).expanduser(),
            raw_data=Path(paths["raw_data"]).expanduser(),
            vault=Path(paths["vault"]).expanduser(),
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
            model=str(llm.get("model", "gpt-5.4-mini")),
        ),
    )


def load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = clean_dotenv_value(value)
        if not key or key in os.environ:
            continue

        os.environ[key] = value
        loaded[key] = value

    return loaded


def clean_dotenv_value(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1]
    return cleaned.strip()
