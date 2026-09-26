"""Keep one successful repair as a lint patch or a lesson file.

A failed repair writes nothing. A lint patch lands in the named file
and wins over a lesson. A lesson is one markdown file named by the
repair SHA, marked ``lokay.lesson/<repair>``.
"""

from __future__ import annotations

from pathlib import Path


def record(
    worktree: str,
    *,
    succeeded: bool,
    repair: str,
    sha: str,
    lesson: str = "",
    paths: list[str] | None = None,
    lint_patch: dict | None = None,
) -> dict:
    if not succeeded:
        return {"ok": True, "recorded": False, "reason": "repair_not_successful"}
    root = Path(worktree)
    patch = dict(lint_patch or {})
    if patch:
        target = root / str(patch.get("path") or "")
        find, replace = str(patch.get("find") or ""), str(patch.get("replace") or "")
        if not target.is_file() or not find or find not in target.read_text(encoding="utf-8"):
            return {"ok": False, "recorded": False, "reason": "lint_patch_missed"}
        target.write_text(
            target.read_text(encoding="utf-8").replace(find, replace, 1), encoding="utf-8",
        )
        return {"ok": True, "recorded": "lint", "path": str(patch.get("path") or "")}
    text = lesson.strip()
    if not text or not sha:
        return {"ok": False, "recorded": False, "reason": "lesson_empty"}
    dest = root / ".lokay" / "lessons" / f"{sha}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    touched = "\n".join(f"- {path}" for path in (paths or []))
    dest.write_text(
        f"lokay.lesson/{repair}\n\n{text}\n" + (f"\nPaths:\n{touched}\n" if touched else ""),
        encoding="utf-8",
    )
    return {"ok": True, "recorded": "lesson", "path": f".lokay/lessons/{sha}.md"}


def relevant(worktree: str, paths: list[str] | None) -> str:
    """Lessons whose recorded paths touch the next diff. Others stay quiet."""
    root = Path(worktree) / ".lokay" / "lessons"
    if not root.is_dir():
        return ""
    wanted = {path.strip() for path in (paths or []) if path.strip()}
    if not wanted:
        return ""
    kept: list[str] = []
    for lesson in sorted(root.glob("*.md")):
        text = lesson.read_text(encoding="utf-8")
        if any(path in text for path in wanted):
            kept.append(text.strip())
    return "\n\n".join(kept)
