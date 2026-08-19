"""Small, JSON-serializable observability for read-only semantic agent calls."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SemanticTrace:
    kind: str
    source: str  # agent | fallback | bypass
    status: str  # completed | disabled | timeout | invalid_json | executor_failed | rejected
    duration_ms: int = 0
    session_kind: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
