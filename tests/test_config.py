from pathlib import Path
import os

from media_to_wiki_convertor.config import load_config, load_dotenv


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
