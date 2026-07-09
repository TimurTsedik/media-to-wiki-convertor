from pathlib import Path
import tomllib


def test_package_metadata_uses_media_to_wiki_convertor_name() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert data["project"]["name"] == "media-to-wiki-convertor"
    assert data["project"]["scripts"]["media-to-wiki-convertor"] == (
        "media_to_wiki_convertor.cli:main"
    )
    assert data["tool"]["setuptools"]["packages"]["find"]["include"] == [
        "media_to_wiki_convertor*"
    ]
