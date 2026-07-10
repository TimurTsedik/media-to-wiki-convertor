from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Literal


RunEventStatus = Literal["started", "skipped", "success", "failed"]


def utc_now() -> datetime:
    return datetime.now(UTC)


def format_wall_time(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


@dataclass(frozen=True)
class RunEventWriter:
    raw_data: Path

    @property
    def path(self) -> Path:
        return self.raw_data / "logs" / "run-events.jsonl"

    def write(
        self,
        *,
        stage: str,
        item_id: str,
        status: RunEventStatus,
        started_at: datetime,
        finished_at: datetime,
        message: str,
        error: str | None = None,
    ) -> None:
        elapsed = max(0.0, (finished_at - started_at).total_seconds())
        event: dict[str, object] = {
            "timestamp": finished_at.isoformat(),
            "stage": stage,
            "item_id": item_id,
            "status": status,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "elapsed_seconds": elapsed,
            "message": message,
        }
        if error is not None:
            event["error"] = error

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(event, ensure_ascii=False) + "\n")
