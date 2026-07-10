from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactIssue:
    severity: str
    path: Path
    message: str


def validate_artifacts(raw_data: Path) -> list[ArtifactIssue]:
    issues: list[ArtifactIssue] = []
    issues.extend(validate_chunk_artifacts(raw_data))
    issues.extend(validate_knowledge_artifacts(raw_data))
    issues.extend(validate_markdown_artifacts(raw_data / "draft_articles"))
    issues.extend(validate_markdown_artifacts(raw_data / "course_materials"))
    return issues


def validate_chunk_artifacts(raw_data: Path) -> list[ArtifactIssue]:
    issues: list[ArtifactIssue] = []
    chunks_dir = raw_data / "chunks"
    if not chunks_dir.exists():
        return issues

    for json_path in sorted(chunks_dir.glob("*/*.json")):
        payload = read_json_object(json_path, issues)
        if payload is None:
            continue

        video_id = json_path.parent.name
        chunk_id = json_path.stem
        md_path = json_path.with_suffix(".md")
        if not md_path.exists() or md_path.stat().st_size == 0:
            issues.append(ArtifactIssue("error", md_path, "Missing chunk markdown sidecar"))
        if str(payload.get("video_id", "")) != video_id:
            issues.append(ArtifactIssue("error", json_path, "Chunk video id does not match path"))
        if str(payload.get("chunk_id", "")) != chunk_id:
            issues.append(ArtifactIssue("error", json_path, "Chunk id does not match filename"))
        if not str(payload.get("text", "")).strip():
            issues.append(ArtifactIssue("error", json_path, "Chunk text is empty"))

    return issues


def validate_knowledge_artifacts(raw_data: Path) -> list[ArtifactIssue]:
    issues: list[ArtifactIssue] = []
    knowledge_dir = raw_data / "extracted_knowledge"
    if not knowledge_dir.exists():
        return issues

    for json_path in sorted(knowledge_dir.glob("*/*.json")):
        payload = read_json_object(json_path, issues)
        if payload is None:
            continue

        source = payload.get("source")
        if not isinstance(source, dict):
            issues.append(ArtifactIssue("error", json_path, "Knowledge source is missing"))
            continue
        if str(source.get("video_id", "")) != json_path.parent.name or str(
            source.get("chunk_id", "")
        ) != json_path.stem:
            issues.append(ArtifactIssue("error", json_path, "Knowledge source does not match path"))

    return issues


def validate_markdown_artifacts(directory: Path) -> list[ArtifactIssue]:
    issues: list[ArtifactIssue] = []
    if not directory.exists():
        return issues

    for path in sorted(directory.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            issues.append(ArtifactIssue("error", path, "Cannot read markdown artifact"))
            continue
        if not text.strip():
            issues.append(ArtifactIssue("error", path, "Markdown artifact is empty"))
            continue
        if not any(line.startswith("# ") for line in text.splitlines()):
            issues.append(
                ArtifactIssue("error", path, "Markdown artifact is missing a top-level heading")
            )

    return issues


def read_json_object(path: Path, issues: list[ArtifactIssue]) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        issues.append(ArtifactIssue("error", path, "Invalid JSON artifact"))
        return None

    if not isinstance(payload, dict):
        issues.append(ArtifactIssue("error", path, "JSON artifact must be an object"))
        return None
    return payload
