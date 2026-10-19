from __future__ import annotations

import json
from pathlib import Path

from lokay import store
from lokay.effects.pi import pi_step
from lokay.safety import untrusted_issue_block

DIFFICULTIES = ("easy", "medium", "hard", "too_big")


def issue_kind(title: str | None) -> str | None:
    if title is not None:
        if title.startswith("[docs-audit]"):
            return "docs_change"
        if title.startswith(("[code-audit]", "[test-audit]")):
            return "code"
    return None


def difficulty_questions(title: str, body: str | None) -> dict:
    return {"state": {"title": title, "body": body or ""}, "questions": [{
        "id": "difficulty", "type": "choice",
        "instructions": "Rate implementation difficulty for one PR.",
        "options": dict(zip(DIFFICULTIES, ("one implementation candidate (k=1)",
                                          "two implementation candidates (k=2)",
                                          "three implementation candidates (k=3)",
                                          "split into smaller tasks"))),
    }]}


def validate_tasks(data: object) -> list[dict]:
    if not isinstance(data, list) or len(data) < 2:
        raise ValueError("split requires at least two tasks")
    for task in data:
        if not isinstance(task, dict) or any(
                not isinstance(task.get(key), str) or not task[key].strip() for key in ("title", "body")):
            raise ValueError("split task requires nonempty title and body")
    return [{"title": task["title"].strip(), "body": task["body"].strip()} for task in data]


def split_tasks(prompt: str, artifact: Path, *, cwd: Path | None = None) -> dict:
    store.remove_file(artifact)
    payload = pi_step(prompt + "\nList at least two smaller, independently mergeable tasks. "
                      "Write only a JSON array of objects with nonempty title and body to "
                      + str(artifact) + ". Do not create issues or modify repository files.", artifact, cwd=cwd)
    if payload["result"] != "done":
        return payload
    try:
        tasks = validate_tasks(json.loads(artifact.read_text()))
    except (ValueError, OSError) as exc:
        return {"result": "failed", "reason": f"invalid split: {exc}"}
    return {"result": "done", "tasks": tasks}


def prompt_for(title: str, body: str | None) -> str:
    return untrusted_issue_block(title, body)
