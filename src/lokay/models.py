from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Issue:
    repo: str
    number: int
    title: str
    body: str
    labels: list[str]
    assignees: list[str]
    url: str
    state: str = "OPEN"
    author: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Issue:
        return cls(
            repo=str(data["repo"]),
            number=int(data["number"]),
            title=str(data.get("title") or ""),
            body=str(data.get("body") or ""),
            labels=list(data.get("labels") or []),
            assignees=list(data.get("assignees") or []),
            url=str(data.get("url") or ""),
            state=str(data.get("state") or "OPEN").upper(),
            author=str(data.get("author") or ""),
        )


@dataclass
class PullRequest:
    repo: str
    number: int
    title: str
    body: str
    head_ref: str
    head_sha: str
    author: str
    url: str
    is_draft: bool
    mergeable: str | None
    labels: list[str] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PullRequest:
        return cls(
            repo=str(data["repo"]),
            number=int(data["number"]),
            title=str(data.get("title") or ""),
            body=str(data.get("body") or ""),
            head_ref=str(data.get("head_ref") or ""),
            head_sha=str(data.get("head_sha") or ""),
            author=str(data.get("author") or ""),
            url=str(data.get("url") or ""),
            is_draft=bool(data.get("is_draft")),
            mergeable=data.get("mergeable"),
            labels=(
                list(data["labels"]) if isinstance(data.get("labels"), list) else None
            ),
        )
