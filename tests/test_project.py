from pathlib import Path

from media_to_wiki_convertor.project import ProjectSettings, init_project, update_project_config


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
    env_example = (target / ".env.example").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=" in env_example
    assert "ANTHROPIC_API_KEY=" in env_example
    assert "GEMINI_API_KEY=" in env_example
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
