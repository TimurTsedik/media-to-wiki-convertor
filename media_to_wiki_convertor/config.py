from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_NAME = "config.toml"
EXAMPLE_CONFIG_PATH = PACKAGE_ROOT / "config.example.toml"
DOTENV_NAME = ".env"
DEFAULT_MEDIA_EXTENSIONS = (
    ".mp4",
    ".mov",
    ".mkv",
    ".mp3",
    ".m4a",
    ".wav",
    ".flac",
    ".aac",
    ".ogg",
    ".opus",
)


@dataclass(frozen=True)
class PipelinePaths:
    video_source: Path
    raw_data: Path
    vault: Path

    @property
    def media_source(self) -> Path:
        return self.video_source


@dataclass(frozen=True)
class DiscoverConfig:
    video_extensions: tuple[str, ...]
    max_depth: int

    @property
    def media_extensions(self) -> tuple[str, ...]:
        return self.video_extensions


@dataclass(frozen=True)
class TranscriptionConfig:
    engine: str
    model: str
    language: str


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    base_url: str = "https://api.openai.com/v1/responses"
    api_key_env: str = "OPENAI_API_KEY"


@dataclass(frozen=True)
class WikiConfig:
    language: str


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
    wiki: WikiConfig
    chunking: ChunkingConfig


def default_llm_base_url(provider: str) -> str:
    if provider == "anthropic":
        return "https://api.anthropic.com/v1/messages"
    if provider == "gemini":
        return "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    return "https://api.openai.com/v1/responses"


def default_llm_api_key_env(provider: str) -> str:
    if provider == "anthropic":
        return "ANTHROPIC_API_KEY"
    if provider == "gemini":
        return "GEMINI_API_KEY"
    return "OPENAI_API_KEY"


def load_config(config_path: Path | None = None) -> PipelineConfig:
    path = resolve_config_path(config_path)
    load_dotenv(path.parent / DOTENV_NAME)

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    paths = data["paths"]
    discover = data.get("discover", {})
    transcription = data.get("transcription", {})
    llm = data.get("llm", {})
    wiki = data.get("wiki", {})
    chunking = data.get("chunking", {})
    provider = str(llm.get("provider", "openai"))
    legacy_language = data.get("language")
    transcription_language = str(transcription.get("language", legacy_language or "ru"))
    wiki_language = str(wiki.get("language", legacy_language or transcription_language))
    base_dir = path.parent

    discover_extensions = discover.get(
        "media_extensions",
        discover.get("video_extensions", DEFAULT_MEDIA_EXTENSIONS),
    )

    return PipelineConfig(
        paths=PipelinePaths(
            video_source=resolve_project_path(base_dir, paths["video_source"]),
            raw_data=resolve_project_path(base_dir, paths["raw_data"]),
            vault=resolve_project_path(base_dir, paths["vault"]),
        ),
        discover=DiscoverConfig(
            video_extensions=tuple(ext.lower() for ext in discover_extensions),
            max_depth=int(discover.get("max_depth", 8)),
        ),
        transcription=TranscriptionConfig(
            engine=str(transcription.get("engine", "mlx-whisper")),
            model=str(transcription.get("model", "mlx-community/whisper-medium")),
            language=transcription_language,
        ),
        llm=LLMConfig(
            provider=provider,
            model=str(llm.get("model", "gpt-5.4-mini")),
            base_url=str(llm.get("base_url", default_llm_base_url(provider))),
            api_key_env=str(llm.get("api_key_env", default_llm_api_key_env(provider))),
        ),
        wiki=WikiConfig(language=wiki_language),
        chunking=ChunkingConfig(
            chunk_minutes=int(chunking.get("chunk_minutes", llm.get("chunk_minutes", 10))),
            overlap_seconds=int(chunking.get("overlap_seconds", 120)),
        ),
    )


def resolve_config_path(config_path: Path | None = None) -> Path:
    if config_path is not None:
        path = config_path.expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path

    project_config = Path.cwd() / DEFAULT_CONFIG_NAME
    if project_config.exists():
        return project_config
    return EXAMPLE_CONFIG_PATH


def resolve_project_path(base_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return base_dir / path


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
