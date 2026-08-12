"""Deterministic approach plan for intentional issues (trust-with-evidence).

Writes evidence onto the branch (``.lokay/approach.md``) before ``run_agent``.
Not a human approval gate and not NEEDS_HUMAN by default.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from lokay.models import Issue

APPROACH_REL_PATH = ".lokay/approach.md"

_HEADING = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
_PATH_TICK = re.compile(
    r"`((?:[\w.-]+/)*[\w.-]+\.[A-Za-z0-9]{1,12})`"
)
_PATH_BARE = re.compile(
    r"(?<![`\w/])((?:src|tests|docs|fala|scripts|config)(?:/[\w.-]+)+\.[A-Za-z0-9]{1,12})"
)
_CHECKBOX = re.compile(r"(?m)^\s*[-*]\s*\[[ xX]\]\s+(.+)$")

_GOAL_HEADINGS = frozenset(
    {
        "goal",
        "goals",
        "summary",
        "problem",
        "what",
        "intent",
        "ship",
    }
)
_TEST_HEADINGS = frozenset(
    {
        "test",
        "tests",
        "test plan",
        "verify",
        "verification",
        "done means",
        "acceptance",
        "acceptance criteria",
    }
)
_NONGOAL_HEADINGS = frozenset(
    {
        "out of scope",
        "out-of-scope",
        "non-goals",
        "nongoals",
        "not in this scope",
        "not in scope",
        "explicitly not in this issue",
    }
)


@dataclass(frozen=True)
class ApproachPlan:
    repo: str
    issue: int
    title: str
    goal: str
    files_likely: tuple[str, ...] = ()
    test_plan: tuple[str, ...] = ()
    non_goals: tuple[str, ...] = ()
    source: str = "deterministic"
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm_heading(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _sections(body: str) -> list[tuple[str, str]]:
    """Return (heading, body) pairs; preamble uses heading ''."""
    text = body or ""
    matches = list(_HEADING.finditer(text))
    if not matches:
        return [("", text.strip())] if text.strip() else []
    out: list[tuple[str, str]] = []
    if matches[0].start() > 0:
        pre = text[: matches[0].start()].strip()
        if pre:
            out.append(("", pre))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((_norm_heading(match.group(2)), text[start:end].strip()))
    return out


def _section_text(sections: list[tuple[str, str]], names: Iterable[str]) -> str:
    want = {_norm_heading(n) for n in names}
    chunks = [body for heading, body in sections if heading in want and body]
    return "\n\n".join(chunks).strip()


def _bullet_lines(text: str) -> tuple[str, ...]:
    lines: list[str] = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        s = re.sub(r"^[-*+]\s+", "", s)
        s = re.sub(r"^\[[ xX]\]\s*", "", s)
        if s:
            lines.append(s)
    return tuple(dict.fromkeys(lines))


def extract_paths(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for match in _PATH_TICK.finditer(text or ""):
        found.append(match.group(1))
    for match in _PATH_BARE.finditer(text or ""):
        found.append(match.group(1))
    # de-dupe, preserve order
    return tuple(dict.fromkeys(found))


def repo_file_hints(worktree: Path | None, candidates: Iterable[str]) -> tuple[str, ...]:
    """Keep path candidates that exist under the worktree (when available)."""
    if worktree is None or not worktree.is_dir():
        return tuple(dict.fromkeys(str(c) for c in candidates if str(c).strip()))
    kept: list[str] = []
    for raw in candidates:
        rel = str(raw).strip().lstrip("./")
        if not rel:
            continue
        if (worktree / rel).exists():
            kept.append(rel)
        else:
            # Still keep explicit issue paths as hints even if not yet created.
            kept.append(rel)
    return tuple(dict.fromkeys(kept))


def _goal_from_issue(issue: Issue, sections: list[tuple[str, str]]) -> str:
    section = _section_text(sections, _GOAL_HEADINGS)
    if section:
        first = section.strip().split("\n\n", 1)[0].strip()
        return first[:800]
    # Preamble / first non-empty paragraph after title echo.
    for heading, body in sections:
        if heading in _NONGOAL_HEADINGS or heading in _TEST_HEADINGS:
            continue
        para = (body or "").strip().split("\n\n", 1)[0].strip()
        if para and para.lower() != (issue.title or "").strip().lower():
            return para[:800]
    title = (issue.title or "").strip()
    return title or f"Implement {issue.repo}#{issue.number}"


def _test_plan(sections: list[tuple[str, str]], body: str) -> tuple[str, ...]:
    section = _section_text(sections, _TEST_HEADINGS)
    items = list(_bullet_lines(section)) if section else []
    if not items:
        boxes = [m.group(1).strip() for m in _CHECKBOX.finditer(body or "") if m.group(1).strip()]
        items.extend(boxes[:8])
    if not items:
        blob = (body or "").lower()
        if "pytest" in blob or "uv run pytest" in blob:
            items.append("Run targeted pytest for touched modules")
        else:
            items.append("Run the smallest useful tests for files touched")
    return tuple(dict.fromkeys(items))[:12]


def _non_goals(sections: list[tuple[str, str]]) -> tuple[str, ...]:
    section = _section_text(sections, _NONGOAL_HEADINGS)
    if not section:
        return ()
    return _bullet_lines(section)[:12]


def build_approach(
    issue: Issue,
    *,
    worktree: Path | None = None,
) -> ApproachPlan:
    """Pure deterministic plan from issue body (+ optional worktree path hints)."""
    sections = _sections(issue.body or "")
    blob = f"{issue.title or ''}\n{issue.body or ''}"
    paths = repo_file_hints(worktree, extract_paths(blob))
    notes: list[str] = [
        "Trust intentional issue; this plan is evidence for later review, not a human gate.",
        "Coding agent may refine details but should stay on the stated goal and non-goals.",
    ]
    if not paths:
        notes.append("No explicit file paths in issue; infer from repo inspection.")
    return ApproachPlan(
        repo=issue.repo,
        issue=int(issue.number),
        title=(issue.title or "").strip(),
        goal=_goal_from_issue(issue, sections),
        files_likely=paths,
        test_plan=_test_plan(sections, issue.body or ""),
        non_goals=_non_goals(sections),
        source="deterministic",
        notes=tuple(notes),
    )


def render_approach_md(plan: ApproachPlan) -> str:
    files = "\n".join(f"- `{p}`" for p in plan.files_likely) or "- (infer from repo inspection)"
    tests = "\n".join(f"- {t}" for t in plan.test_plan) or "- Run targeted tests"
    nongoals = "\n".join(f"- {n}" for n in plan.non_goals) or "- (none stated)"
    notes = "\n".join(f"- {n}" for n in plan.notes)
    return (
        f"# Approach plan\n\n"
        f"<!-- lokay-approach source={plan.source} repo={plan.repo} issue={plan.issue} -->\n\n"
        f"Repository: `{plan.repo}`  \n"
        f"Issue: #{plan.issue} — {plan.title}\n\n"
        f"## Goal\n\n{plan.goal}\n\n"
        f"## Files likely touched\n\n{files}\n\n"
        f"## Test plan\n\n{tests}\n\n"
        f"## Non-goals\n\n{nongoals}\n\n"
        f"## Notes\n\n{notes}\n"
    )


def write_approach_file(worktree: Path, content: str, *, rel_path: str = APPROACH_REL_PATH) -> Path:
    path = Path(worktree) / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def approach_present_in_diff(diff_text: str, *, rel_path: str = APPROACH_REL_PATH) -> bool:
    """Soft signal: true when the PR diff touches the approach artifact."""
    needle = rel_path.replace("\\", "/")
    text = diff_text or ""
    if needle in text:
        return True
    # git diff headers sometimes show a/b prefixes
    return f"a/{needle}" in text or f"b/{needle}" in text


def approach_excerpt_from_diff(
    diff_text: str, *, rel_path: str = APPROACH_REL_PATH, limit: int = 2000
) -> str:
    """Best-effort excerpt of added approach.md lines from a unified diff."""
    if not approach_present_in_diff(diff_text, rel_path=rel_path):
        return ""
    lines: list[str] = []
    in_file = False
    for line in (diff_text or "").splitlines():
        if line.startswith("diff --git"):
            in_file = rel_path in line
            continue
        if not in_file:
            continue
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
        if sum(len(x) + 1 for x in lines) >= limit:
            break
    return "\n".join(lines)[:limit]
