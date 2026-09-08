"""Read an already prepared dashboard; never start product computation."""

from datetime import datetime, timezone
from pathlib import Path
import uuid
from typing import Any
import json
import math

MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024


class SnapshotUnavailable(ValueError):
    """No usable dashboard artifact is available."""


def write_snapshot(path: Path, data: dict[str, Any]) -> Path:
    """Atomically write a validated dashboard snapshot JSON."""
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp.{uuid.uuid4().hex[:8]}")
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(target)
    return target


def read_snapshot(path: Path, *, max_age: float = 120, now: datetime | None = None) -> dict[str, Any]:
    """Read one bounded artifact, preserving its source timestamp and data."""
    if not math.isfinite(max_age) or max_age <= 0:
        raise ValueError("max_age must be finite and positive")
    try:
        with path.open("rb") as source:
            raw = source.read(MAX_SNAPSHOT_BYTES + 1)
        if len(raw) > MAX_SNAPSHOT_BYTES:
            raise ValueError("oversize snapshot")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("snapshot must be an object")
        for key in ("status", "health", "throughput", "kpis", "backlog"):
            if not isinstance(data.get(key), dict):
                raise ValueError("invalid snapshot section")
        for key in ("catalog", "history"):
            if not isinstance(data.get(key), list) or not all(
                isinstance(row, dict) for row in data[key]
            ):
                raise ValueError("invalid snapshot rows")
        if not isinstance(data["status"].get("ok"), bool):
            raise ValueError("invalid status readiness")
        def require_rows(value: Any) -> None:
            if value is not None and (not isinstance(value, list) or not all(
                isinstance(row, dict) for row in value
            )):
                raise ValueError("invalid nested rows")

        def require_receipt(value: Any) -> None:
            if value is None:
                return
            if not isinstance(value, dict):
                raise ValueError("invalid receipt")
            remaining = value.get("remaining")
            if remaining is not None:
                if not isinstance(remaining, dict):
                    raise ValueError("invalid remaining queues")
                require_rows(remaining.get("by_repo"))

        require_receipt(data["status"].get("last_pass"))
        require_rows(data["status"].get("by_repo"))
        for receipt in data["history"]:
            require_receipt(receipt)
        if not all(isinstance(metrics, dict) for metrics in data["throughput"].values()):
            raise ValueError("invalid throughput metrics")
        generated = datetime.fromisoformat(data["generated_at"])
        if generated.tzinfo is None:
            raise ValueError("timestamp requires timezone")
        age = ((now or datetime.now(timezone.utc)) - generated).total_seconds()
        if age < 0:
            raise ValueError("snapshot timestamp is in the future")
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        # Never disclose paths or artifact content to HTTP clients.
        raise SnapshotUnavailable("dashboard snapshot unavailable") from exc
    return {**data, "snapshot_age_seconds": age, "snapshot_stale": age > max_age}
