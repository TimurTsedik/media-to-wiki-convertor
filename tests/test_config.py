from pathlib import Path
import os

from media_to_wiki_convertor.config import DiscoverConfig, PipelinePaths, load_config, load_dotenv


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

[llm]
provider = "openai-compatible"
model = "gpt-5.4-mini"
base_url = "https://llm.example.test/v1/responses"
api_key_env = "CUSTOM_LLM_API_KEY"

[wiki]
language = "en"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.paths.video_source == Path("/video")
    assert config.paths.raw_data == Path("/raw")
    assert config.paths.vault == Path("/vault")
    assert config.discover.video_extensions == (".mp4", ".mov")
    assert config.discover.max_depth == 3
    assert config.llm.provider == "openai-compatible"
    assert config.llm.model == "gpt-5.4-mini"
    assert config.llm.base_url == "https://llm.example.test/v1/responses"
    assert config.llm.api_key_env == "CUSTOM_LLM_API_KEY"
    assert config.transcription.language == "ru"
    assert config.wiki.language == "en"


def test_pipeline_paths_exposes_media_source_alias() -> None:
    paths = PipelinePaths(
        video_source=Path("/recordings"),
        raw_data=Path("/raw"),
        vault=Path("/vault"),
    )

    assert paths.media_source == Path("/recordings")


def test_discover_config_exposes_media_extensions_alias() -> None:
    discover = DiscoverConfig(video_extensions=(".mp3", ".m4a"), max_depth=4)

    assert discover.media_extensions == (".mp3", ".m4a")


def test_load_config_supports_legacy_top_level_language(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
language = "en"

[paths]
video_source = "/video"
raw_data = "/raw"
vault = "/vault"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.transcription.language == "en"
    assert config.wiki.language == "en"
    assert config.llm.provider == "openai"
    assert config.llm.model == "gpt-5.4-mini"
    assert config.llm.base_url == "https://api.openai.com/v1/responses"
    assert config.llm.api_key_env == "OPENAI_API_KEY"
    assert ".mp3" in config.discover.video_extensions
    assert ".m4a" in config.discover.video_extensions
    assert ".wav" in config.discover.video_extensions


def test_load_config_accepts_media_extensions(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[paths]
video_source = "/recordings"
raw_data = "/raw"
vault = "/vault"

[discover]
media_extensions = [".mp3", ".M4A"]
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.discover.video_extensions == (".mp3", ".m4a")


def test_load_config_defaults_anthropic_llm_endpoint_and_api_key_env(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[paths]
video_source = "/video"
raw_data = "/raw"
vault = "/vault"

[llm]
provider = "anthropic"
model = "claude-test"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.llm.provider == "anthropic"
    assert config.llm.base_url == "https://api.anthropic.com/v1/messages"
    assert config.llm.api_key_env == "ANTHROPIC_API_KEY"


def test_load_config_preserves_explicit_anthropic_openai_api_key_env(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[paths]
video_source = "/video"
raw_data = "/raw"
vault = "/vault"

[llm]
provider = "anthropic"
model = "claude-test"
api_key_env = "OPENAI_API_KEY"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.llm.provider == "anthropic"
    assert config.llm.api_key_env == "OPENAI_API_KEY"


def test_load_config_defaults_gemini_llm_endpoint_and_api_key_env(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[paths]
video_source = "/video"
raw_data = "/raw"
vault = "/vault"

[llm]
provider = "gemini"
model = "gemini-test"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.llm.provider == "gemini"
    assert (
        config.llm.base_url
        == "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )
    assert config.llm.api_key_env == "GEMINI_API_KEY"


def test_load_config_defaults_wiki_language_to_transcription_language(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[paths]
video_source = "/video"
raw_data = "/raw"
vault = "/vault"

[transcription]
language = "en"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.transcription.language == "en"
    assert config.wiki.language == "en"


def test_load_dotenv_sets_missing_values_and_strips_quotes(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        """
# comment
OPENAI_API_KEY="secret-value"
OTHER=value
""".strip(),
        encoding="utf-8",
    )
    old_key = os.environ.pop("OPENAI_API_KEY", None)
    old_other = os.environ.pop("OTHER", None)
    try:
        loaded = load_dotenv(env_path)

        assert loaded == {"OPENAI_API_KEY": "secret-value", "OTHER": "value"}
        assert os.environ["OPENAI_API_KEY"] == "secret-value"
        assert os.environ["OTHER"] == "value"
    finally:
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("OTHER", None)
        if old_key is not None:
            os.environ["OPENAI_API_KEY"] = old_key
        if old_other is not None:
            os.environ["OTHER"] = old_other


def test_load_dotenv_does_not_override_existing_environment(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=file-value\n", encoding="utf-8")
    old_key = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = "shell-value"
    try:
        loaded = load_dotenv(env_path)

        assert loaded == {}
        assert os.environ["OPENAI_API_KEY"] == "shell-value"
    finally:
        if old_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = old_key
