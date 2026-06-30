from pathlib import Path

from larchenko_kb.config import load_config


def test_load_config_from_toml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[paths]
video_source = "/video"
raw_data = "/raw"
vault = "/vault"

[discover]
video_extensions = [".mp4", ".MOV"]
max_depth = 3
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.paths.video_source == Path("/video")
    assert config.paths.raw_data == Path("/raw")
    assert config.paths.vault == Path("/vault")
    assert config.discover.video_extensions == (".mp4", ".mov")
    assert config.discover.max_depth == 3
