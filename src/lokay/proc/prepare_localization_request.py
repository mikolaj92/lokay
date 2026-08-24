"""Prepare one closed localization request from parent Fala facts."""

import json
from pathlib import Path

from lokay.approach_plan import APPROACH_REL_PATH
from lokay.localize import extract_issue_file_paths, has_issue_files_section


def prepare(
    *,
    worktree: str,
    repo: str,
    issue_raw: dict,
    plan: dict,
    checks_text: str,
    review: object,
    extra_paths: list[str],
    max_paths: int,
    rel_path: str,
) -> dict:
    root = Path(worktree)
    title, body = str(issue_raw.get("title") or ""), str(issue_raw.get("body") or "")
    seed_parts = [
        title,
        body,
        checks_text,
        json.dumps(review, ensure_ascii=False, sort_keys=True) if review else "",
    ]
    approach = root / APPROACH_REL_PATH
    if approach.is_file():
        seed_parts.append(approach.read_text(encoding="utf-8"))
    likely = (plan.get("plan") or {}).get("files_likely") or []
    extras = list(
        dict.fromkeys(str(x).strip() for x in [*extra_paths, *likely] if str(x).strip())
    )
    seed = "\n\n".join(x for x in seed_parts if x.strip())
    explicit = list(extract_issue_file_paths(body))
    return {
        "ok": True,
        "worktree": str(root),
        "repo": repo or str(issue_raw.get("repo") or ""),
        "issue": int(issue_raw.get("number") or 0),
        "seed": seed,
        "extras": extras,
        "max_paths": max(1, int(max_paths or 40)),
        "rel_path": rel_path,
        "explicit_issue_paths": explicit,
        "has_file_hints": bool(has_issue_files_section(body) or explicit),
    }
