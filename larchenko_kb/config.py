from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.toml"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "config.example.toml"


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
class PipelineConfig:
    paths: PipelinePaths
    discover: DiscoverConfig


def load_config(config_path: Path | None = None) -> PipelineConfig:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        path = EXAMPLE_CONFIG_PATH

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    paths = data["paths"]
    discover = data.get("discover", {})

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
    )
