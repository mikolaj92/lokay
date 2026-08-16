"""Deterministic issue intake: CLOSE | READY | SPLIT | NEEDS_HUMAN.

Cheap, testable checks that harden inbox triage before `ai:ready` sticks
eligible for `issue_to_pr`. Pure rules first; no coding harness.

Product law: humans author intentional issues; the mill consumes. Trust the
operator/assignee — prefer READY+implement autonomy; do not invent distrustful
human gates. CLOSE / SPLIT / READY+implement are the default exits.
CLOSE is for clear obsolete / wrong-shape / superseded cases only — do not
bias toward distrusting every ticket. NEEDS_HUMAN is a rare residual after
rules fail closed — never the escape hatch for oversized work that can be
auto-split.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from lokay.issue_checkboxes import work_checkbox_count
from lokay.models import Issue
from lokay.triage import is_parked, is_undecided

# --- Verdicts for one check ---
PASS = "pass"
CLOSE = "close"
SPLIT = "split"
NEEDS_HUMAN = "needs_human"
INCONCLUSIVE = "inconclusive"

MAX_CHECKBOXES_ONE_PASS = 5

# Issue text that asks for platform-host playbooks (wrong on libraries/kits).
_PLATFORM_HOST_WORK = re.compile(
    r"(?i)\b("
    r"product_shell|basecoat(?:-factory)?"
    r"|/static/platform|static/platform"
    r"|platform\s*ui(?:\s*audit)?"
    r"|adopt\s+(?:full\s+)?(?:basecoat|product_shell|the\s+platform|platform\s+stack)"
    r"|app[_-]?factory\s+compat"
    r"|host\s+shell\s+must\s+extend"
    r")\b"
)

_INVENTORY_BLOB = re.compile(
    r"(?i)\b("
    r"inventory\s+(?:everything|all|the\s+whole)"
    r"|audit\s+(?:everything|all\s+repos?|the\s+entire)"
    r"|enumerate\s+(?:every|all)"
    r"|catalog\s+(?:every|all)"
    r")\b"
)

_MULTI_EPIC = re.compile(r"(?i)\bepic\b")
_TRACKER_TITLE = re.compile(r"(?i)\b(?:tracker|epic)\b")
_TITLE_ONLY_BODY = re.compile(
    r"(?i)^\s*(?:(?:todo|tbd|see\s+title|as\s+title)\.?)\s*$"
)

# Concrete removal/delete of a path named in the issue.
_REMOVE_QUOTED = re.compile(
    r"(?i)\b(?:remove|delete|drop|erase)\s+[`'\"]([^`'\"]+)[`'\"]"
)
_REMOVE_PATH = re.compile(
    r"(?i)\b(?:remove|delete|drop)\s+"
    r"((?:src/|tests/|docs/|scripts/|fala/|compose/)?"
    r"[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)+\.[A-Za-z0-9]+)"
)

# Concrete add/create of a path (feature already present when file exists).
_ADD_QUOTED = re.compile(
    r"(?i)\b(?:add|create|introduce|restore)\s+[`'\"]([^`'\"]+)[`'\"]"
)
_ADD_PATH = re.compile(
    r"(?i)\b(?:add|create|introduce)\s+"
    r"((?:src/|tests/|docs/|scripts/|fala/)?"
    r"[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)+\.[A-Za-z0-9]+)"
)

_ALREADY_ON_MAIN = re.compile(
    r"(?i)\b("
    r"already\s+on\s+main"
    r"|already\s+(?:merged|implemented|present|landed|shipped)"
    r"|landed\s+on\s+main"
    r"|present\s+on\s+main"
    r")\b"
)

_PR_URL = re.compile(
    r"(?i)https?://github\.com/[^/\s]+/[^/\s]+/pull/(\d+)"
)
_PR_HASH = re.compile(r"(?i)\b(?:pr|pull\s*request)\s*#(\d+)\b")
_ISSUE_HASH = re.compile(r"(?:^|[\s(,])#(\d+)\b")
_SUPERSEDED_MARKERS = re.compile(
    r"(?i)\b(superseded\s+by|already\s+(?:done|fixed|merged)|duplicate\s+of)\b"
)

_HOST_FILE_MARKERS = (
    "product_shell",
    "static/platform",
    "platform_theme_locale",
    "platform_auth",
)
_HOST_DIR_MARKERS = (
    "static/platform",
    "templates",
)
_LIBRARY_NAME_HINTS = (
    "kit",
    "library",
    "sdk",
    "crate",
    "package",
)
_WEB_DEP_MARKERS = (
    "fastapi",
    "starlette",
    "flask",
    "django",
    "jinja2",
    "app-factory",
    "app_factory",
)


@dataclass(frozen=True)
class CheckResult:
    """One deterministic intake check."""

    check: str
    verdict: str  # pass | close | split | needs_human | inconclusive
    reason: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IntakeDecision:
    """Aggregated intake outcome for one issue."""

    decision: str  # close | ready | split | needs_human | skip
    reason: str
    checks: tuple[CheckResult, ...] = ()
    add_labels: tuple[str, ...] = ()
    remove_labels: tuple[str, ...] = ()
    close: bool = False
    comment: str | None = None
    implementable: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["checks"] = [c.to_dict() for c in self.checks]
        return data


@dataclass(frozen=True)
class RepoShape:
    """Filesystem heuristics for playbook fitness."""

    kind: str  # host | library | empty | unknown
    signals: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "signals": list(self.signals)}


def _bounded_file_signals(root: Path, *, limit: int = 400) -> tuple[list[str], list[Path]]:
    """Walk a few hundred files for host markers; return signals + html paths."""
    signals: list[str] = []
    html: list[Path] = []
    seen = 0
    skip_dirs = {".git", ".venv", "node_modules", "dist", "build", ".tox", "__pycache__"}
    for dirpath, dirnames, filenames in root.walk():
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for name in filenames:
            seen += 1
            path = Path(dirpath) / name
            rel = str(path.relative_to(root)).replace("\\", "/")
            lower = rel.lower()
            if lower.endswith(".html"):
                html.append(path)
            if "product_shell" in lower:
                signals.append("file:product_shell")
            if "static/platform/" in lower or lower.endswith("static/platform"):
                signals.append("path:static/platform")
            if seen >= limit:
                return signals, html
    return signals, html


def probe_repo_shape(clone_path: Path | None) -> RepoShape:
    """Classify a checkout as host / library / empty / unknown (pure FS)."""
    if clone_path is None:
        return RepoShape(kind="unknown", signals=("no_clone_path",))
    root = Path(clone_path)
    if not root.is_dir():
        return RepoShape(kind="unknown", signals=("clone_missing",))

    signals: list[str] = []
    try:
        entries = [p for p in root.iterdir() if p.name not in {".git", ".venv", "node_modules"}]
    except OSError:
        return RepoShape(kind="unknown", signals=("clone_unreadable",))
    if not entries:
        return RepoShape(kind="empty", signals=("no_entries",))

    text_blobs: list[str] = []
    for rel in ("README.md", "README.rst", "README", "pyproject.toml", "Package.swift"):
        path = root / rel
        if path.is_file():
            try:
                text_blobs.append(path.read_text(encoding="utf-8", errors="replace")[:8000])
            except OSError:
                continue

    joined = "\n".join(text_blobs).lower()
    host_hits = 0
    for marker in _HOST_DIR_MARKERS:
        if (root / marker).exists():
            host_hits += 1
            signals.append(f"dir:{marker}")
    for marker in _HOST_FILE_MARKERS:
        if marker in joined:
            host_hits += 1
            signals.append(f"text:{marker}")

    walk_signals, html_templates = _bounded_file_signals(root)
    signals.extend(walk_signals)
    if "file:product_shell" in walk_signals:
        host_hits += 1
    if "path:static/platform" in walk_signals:
        host_hits += 1
    if html_templates:
        host_hits += 1
        signals.append("html_templates")

    web_dep = any(m in joined for m in _WEB_DEP_MARKERS)
    if web_dep:
        signals.append("web_dependency")

    uniq = tuple(dict.fromkeys(signals))
    if host_hits >= 2 or (host_hits >= 1 and web_dep):
        return RepoShape(kind="host", signals=uniq)

    swift_only = (root / "Package.swift").is_file() and not html_templates and not web_dep
    lib_hint = any(h in joined for h in _LIBRARY_NAME_HINTS)
    name_hint = any(h in root.name.lower() for h in ("kit", "lib", "sdk", "crate"))
    has_src_pkg = (root / "src").is_dir() or (root / "Package.swift").is_file()
    no_web = not html_templates and not web_dep and "product_shell" not in joined
    if no_web and (lib_hint or name_hint or has_src_pkg or swift_only):
        extra = list(uniq)
        if lib_hint:
            extra.append("readme_library_hint")
        if name_hint:
            extra.append("name_library_hint")
        if has_src_pkg:
            extra.append("src_or_swift_package")
        if swift_only:
            extra.append("swift_only")
        return RepoShape(kind="library", signals=tuple(dict.fromkeys(extra)))

    if len(entries) <= 2 and not html_templates:
        return RepoShape(kind="empty", signals=tuple(dict.fromkeys([*uniq, "sparse_tree"])))

    return RepoShape(kind="unknown", signals=uniq)


def issue_requests_platform_host(issue: Issue) -> bool:
    blob = f"{issue.title or ''}\n{issue.body or ''}"
    return bool(_PLATFORM_HOST_WORK.search(blob))


def named_removal_paths(issue: Issue) -> list[str]:
    blob = f"{issue.title or ''}\n{issue.body or ''}"
    found: list[str] = []
    for match in _REMOVE_QUOTED.finditer(blob):
        found.append(match.group(1).strip())
    for match in _REMOVE_PATH.finditer(blob):
        found.append(match.group(1).strip())
    return list(dict.fromkeys(p for p in found if p and ".." not in p and not p.startswith("/")))


def named_add_paths(issue: Issue) -> list[str]:
    blob = f"{issue.title or ''}\n{issue.body or ''}"
    found: list[str] = []
    for match in _ADD_QUOTED.finditer(blob):
        found.append(match.group(1).strip())
    for match in _ADD_PATH.finditer(blob):
        found.append(match.group(1).strip())
    return list(dict.fromkeys(p for p in found if p and ".." not in p and not p.startswith("/")))


def referenced_pr_numbers(issue: Issue) -> list[int]:
    blob = f"{issue.title or ''}\n{issue.body or ''}"
    nums = [int(x) for x in _PR_URL.findall(blob)]
    nums.extend(int(x) for x in _PR_HASH.findall(blob))
    return list(dict.fromkeys(nums))


def checkbox_count(body: str) -> int:
    """Work checkboxes only — template Subsystem/Environment tags do not count."""
    return work_checkbox_count(body)


def check_open(*, state: str | None) -> CheckResult:
    """Issue must still be open upstream."""
    normalized = (state or "OPEN").strip().upper()
    if normalized in {"", "OPEN"}:
        return CheckResult(check="open", verdict=PASS, reason="issue_open", detail={"state": normalized or "OPEN"})
    return CheckResult(
        check="open",
        verdict=CLOSE,
        reason="issue_already_closed",
        detail={"state": normalized},
    )


def check_superseded(
    issue: Issue,
    *,
    merged_prs: Iterable[int] = (),
    closed_tracker_done: bool = False,
    tracker_refs: Iterable[str] = (),
) -> CheckResult:
    """Superseding evidence: merged linked PR or closed/done tracker/epic."""
    merged = sorted({int(x) for x in merged_prs})
    if merged:
        return CheckResult(
            check="superseded",
            verdict=CLOSE,
            reason="linked_pr_merged",
            detail={"merged_prs": merged},
        )
    title = issue.title or ""
    blob = f"{title}\n{issue.body or ''}"
    trackerish = bool(_TRACKER_TITLE.search(title))
    if closed_tracker_done and (
        trackerish or _SUPERSEDED_MARKERS.search(blob) or _MULTI_EPIC.search(title)
    ):
        return CheckResult(
            check="superseded",
            verdict=CLOSE,
            reason="tracker_already_done",
            detail={"tracker_refs": list(tracker_refs)},
        )
    if _SUPERSEDED_MARKERS.search(blob) and merged:
        return CheckResult(
            check="superseded",
            verdict=CLOSE,
            reason="explicit_superseded_marker",
            detail={"tracker_refs": list(tracker_refs), "merged_prs": merged},
        )
    return CheckResult(check="superseded", verdict=PASS, reason="no_supersede_evidence")


def check_duplicate_ai_pr(
    issue: Issue,
    *,
    covering_prs: Iterable[dict[str, Any]] = (),
) -> CheckResult:
    """CLOSE when an open or merged ai/fix PR already covers this issue."""
    rows = [p for p in covering_prs if isinstance(p, dict) and p.get("number")]
    if not rows:
        return CheckResult(check="duplicate_ai_pr", verdict=PASS, reason="no_covering_ai_pr")
    detail = {
        "prs": [
            {
                "number": int(p["number"]),
                "state": str(p.get("state") or "OPEN").upper(),
                "merged": bool(p.get("merged")),
            }
            for p in rows
        ],
        "issue": int(issue.number),
    }
    return CheckResult(
        check="duplicate_ai_pr",
        verdict=CLOSE,
        reason="duplicate_ai_pr_for_issue",
        detail=detail,
    )


def check_shape(issue: Issue, shape: RepoShape) -> CheckResult:
    """Playbook fitness: reject platform-host work on libraries/kits/empty/Swift-only."""
    wants_host = issue_requests_platform_host(issue)
    detail = {"repo_kind": shape.kind, "signals": list(shape.signals), "platform_host_work": wants_host}
    if not wants_host:
        return CheckResult(check="shape", verdict=PASS, reason="not_platform_host_playbook", detail=detail)
    if shape.kind == "host":
        return CheckResult(check="shape", verdict=PASS, reason="host_repo_fit", detail=detail)
    if shape.kind in {"library", "empty"}:
        return CheckResult(
            check="shape",
            verdict=CLOSE,
            reason="wrong_product_shape",
            detail=detail,
        )
    # unknown tree — do not READY platform adoption blindly
    return CheckResult(
        check="shape",
        verdict=NEEDS_HUMAN,
        reason="host_markers_unclear",
        detail=detail,
    )


def check_satisfied(issue: Issue, *, clone_path: Path | None) -> CheckResult:
    """Already-satisfied: removals absent, adds present, or explicit already-on-main."""
    blob = f"{issue.title or ''}\n{issue.body or ''}"
    if _ALREADY_ON_MAIN.search(blob):
        return CheckResult(
            check="satisfied",
            verdict=CLOSE,
            reason="already_on_main_marker",
            detail={},
        )

    remove_paths = named_removal_paths(issue)
    add_paths = named_add_paths(issue)
    if not remove_paths and not add_paths:
        return CheckResult(check="satisfied", verdict=PASS, reason="no_concrete_paths")

    if clone_path is None or not Path(clone_path).is_dir():
        return CheckResult(
            check="satisfied",
            verdict=INCONCLUSIVE,
            reason="clone_unavailable_for_path_check",
            detail={"remove_paths": remove_paths, "add_paths": add_paths},
        )

    root = Path(clone_path)
    detail: dict[str, Any] = {
        "remove_paths": remove_paths,
        "add_paths": add_paths,
    }

    if remove_paths:
        missing = [p for p in remove_paths if not (root / p).exists()]
        present = [p for p in remove_paths if (root / p).exists()]
        detail["already_absent"] = missing
        detail["still_present"] = present
        if not present:
            return CheckResult(
                check="satisfied",
                verdict=CLOSE,
                reason="already_satisfied_on_main",
                detail=detail,
            )

    if add_paths:
        present_adds = [p for p in add_paths if (root / p).exists()]
        missing_adds = [p for p in add_paths if not (root / p).exists()]
        detail["feature_present"] = present_adds
        detail["feature_missing"] = missing_adds
        if present_adds and not missing_adds:
            return CheckResult(
                check="satisfied",
                verdict=CLOSE,
                reason="feature_already_present",
                detail=detail,
            )

    return CheckResult(check="satisfied", verdict=PASS, reason="work_still_needed", detail=detail)


def check_ambiguity(issue: Issue) -> CheckResult:
    """Oversized/multi-part → SPLIT when possible; residual ambiguity → NEEDS_HUMAN."""
    title = (issue.title or "").strip()
    body = (issue.body or "").strip()
    blob = f"{title}\n{body}"

    if _INVENTORY_BLOB.search(blob):
        return CheckResult(
            check="ambiguity",
            verdict=SPLIT,
            reason="inventory_everything",
            detail={},
        )

    epic_hits = len(_MULTI_EPIC.findall(blob))
    title_is_epic = bool(re.search(r"(?i)\bepic\b", title))
    if title_is_epic or epic_hits >= 3 or (epic_hits >= 2 and " and " in title.lower()):
        return CheckResult(
            check="ambiguity",
            verdict=SPLIT,
            reason="multi_epic_blob",
            detail={"epic_mentions": epic_hits, "title_is_epic": title_is_epic},
        )

    boxes = checkbox_count(body)
    if boxes > MAX_CHECKBOXES_ONE_PASS:
        return CheckResult(
            check="ambiguity",
            verdict=SPLIT,
            reason="too_many_checkboxes",
            detail={"checkboxes": boxes},
        )

    if body and _TITLE_ONLY_BODY.match(body):
        return CheckResult(
            check="ambiguity",
            verdict=NEEDS_HUMAN,
            reason="title_only_body",
            detail={},
        )

    # Very wide "audit all" without acceptance criteria bullets — cannot auto-split.
    if re.search(r"(?i)\baudit\b", title) and not re.search(r"(?m)^\s*[-*]\s*\[[ xX]\]", body):
        if len(body) < 120:
            return CheckResult(
                check="ambiguity",
                verdict=NEEDS_HUMAN,
                reason="audit_without_acceptance",
                detail={},
            )

    return CheckResult(check="ambiguity", verdict=PASS, reason="spec_clear_enough")


def aggregate_intake(
    checks: Iterable[CheckResult],
    *,
    ready_label: str = "ai:ready",
    needs_feedback_label: str = "ai:needs-feedback",
    skip: bool = False,
    skip_reason: str = "",
    force_split: bool = False,
) -> IntakeDecision:
    """Aggregate check verdicts → CLOSE | READY | SPLIT | NEEDS_HUMAN | skip."""
    checked = tuple(checks)
    if skip:
        return IntakeDecision(
            decision="skip",
            reason=skip_reason or "skip",
            checks=checked,
            implementable=False,
        )

    close_hit = next((c for c in checked if c.verdict == CLOSE), None)
    if close_hit is not None:
        comment = _close_comment(close_hit, checked)
        return IntakeDecision(
            decision="close",
            reason=close_hit.reason,
            checks=checked,
            remove_labels=(ready_label,),
            close=True,
            comment=comment,
            implementable=False,
        )

    split_hit = next((c for c in checked if c.verdict == SPLIT), None)
    if split_hit is not None or force_split:
        hit = split_hit or CheckResult(
            check="ambiguity",
            verdict=SPLIT,
            reason="triage_split_candidate",
            detail={},
        )
        return IntakeDecision(
            decision="split",
            reason=hit.reason,
            checks=checked,
            remove_labels=(ready_label,),
            comment=_split_comment(hit),
            implementable=False,
        )

    human_hit = next((c for c in checked if c.verdict == NEEDS_HUMAN), None)
    if human_hit is not None:
        return IntakeDecision(
            decision="needs_human",
            reason=human_hit.reason,
            checks=checked,
            add_labels=(needs_feedback_label,),
            remove_labels=(ready_label,),
            comment=_needs_human_comment(human_hit),
            implementable=False,
        )

    inconclusive = [c for c in checked if c.verdict == INCONCLUSIVE]
    if inconclusive:
        # Fail closed: do not READY when evidence is missing.
        hit = inconclusive[0]
        return IntakeDecision(
            decision="needs_human",
            reason=f"inconclusive_{hit.reason}",
            checks=checked,
            add_labels=(needs_feedback_label,),
            remove_labels=(ready_label,),
            comment=(
                f"Needs feedback: intake check incomplete ({hit.check}: {hit.reason}). "
                "Clarify paths or ensure clone is available, then drop this label."
            ),
            implementable=False,
        )

    return IntakeDecision(
        decision="ready",
        reason="intake_ok",
        checks=checked,
        add_labels=(ready_label,),
        implementable=True,
        comment=None,
    )


def _close_comment(hit: CheckResult, checks: tuple[CheckResult, ...]) -> str:
    reasons = ", ".join(f"{c.check}={c.reason}" for c in checks if c.verdict == CLOSE)
    if hit.reason == "wrong_product_shape":
        kind = (hit.detail or {}).get("repo_kind", "non-host")
        return (
            f"Closed (intake): platform-host/Basecoat playbook on {kind!r} repo "
            "(library/kit/empty/Swift-only). Reopen on a real web host if needed."
        )
    if hit.reason == "already_satisfied_on_main":
        absent = ", ".join((hit.detail or {}).get("already_absent") or []) or "named paths"
        return f"Closed (intake): removal targets already absent on main ({absent})."
    if hit.reason == "feature_already_present":
        present = ", ".join((hit.detail or {}).get("feature_present") or []) or "named paths"
        return f"Closed (intake): add targets already present on main ({present})."
    if hit.reason == "already_on_main_marker":
        return "Closed (intake): issue states work is already on main / implemented."
    if hit.reason == "linked_pr_merged":
        prs = ", ".join(f"#{n}" for n in (hit.detail or {}).get("merged_prs") or [])
        return f"Closed (intake): linked PR(s) merged ({prs or 'see body'})."
    if hit.reason == "tracker_already_done":
        return "Closed (intake): tracker/epic already closed or superseded by merged work."
    if hit.reason == "duplicate_ai_pr_for_issue":
        prs = ", ".join(
            f"#{p.get('number')}" for p in (hit.detail or {}).get("prs") or [] if p.get("number")
        )
        return f"Closed (intake): duplicate of existing AI PR ({prs or 'see branch'})."
    if hit.reason == "issue_already_closed":
        return "Closed (intake): already closed upstream."
    return f"Closed (intake): {reasons or hit.reason}."


def _split_comment(hit: CheckResult) -> str:
    return (
        f"Split queued (intake: {hit.reason}). "
        "Parent will become a tracker; child issues get the implementable slices."
    )


def _needs_human_comment(hit: CheckResult) -> str:
    return (
        f"Needs feedback (rare): intake will not mark ai:ready ({hit.check}: {hit.reason}). "
        "Clarify a single implementable ask, then remove this label."
    )


def should_run_intake(
    issue_labels: list[str],
    *,
    ready_label: str,
    needs_feedback_label: str,
    blocked_label: str,
    candidate_ready: bool = False,
    candidate_split: bool = False,
) -> tuple[bool, str]:
    """Intake runs for ready/split candidates; skips parked / undecided / human-parked."""
    if is_parked(issue_labels):
        return False, "parked_frozen"
    labels = set(issue_labels)
    if ready_label in labels:
        return True, "already_ready"
    if candidate_split:
        return True, "triage_split_candidate"
    if candidate_ready:
        # Upstream triage decided ready (including dry-run where labels are not applied).
        return True, "triage_ready_candidate"
    if blocked_label in labels:
        return False, "blocked"
    if needs_feedback_label in labels:
        return False, "needs_feedback"
    # Undecided inbox: triage_issue should have run first in issue_triage.
    # If somehow still undecided, skip (do not READY from intake alone).
    if is_undecided(
        issue_labels,
        ready_label=ready_label,
        blocked_label=blocked_label,
        needs_feedback_label=needs_feedback_label,
    ):
        return False, "undecided_await_triage"
    return False, "not_ready_candidate"


def decide_intake(
    issue: Issue,
    *,
    state: str | None = "OPEN",
    clone_path: Path | None = None,
    merged_prs: Iterable[int] = (),
    covering_prs: Iterable[dict[str, Any]] = (),
    closed_tracker_done: bool = False,
    tracker_refs: Iterable[str] = (),
    ready_label: str = "ai:ready",
    needs_feedback_label: str = "ai:needs-feedback",
    run: bool = True,
    skip_reason: str = "",
    force_split: bool = False,
) -> IntakeDecision:
    """Run all deterministic checks and aggregate (pure aside from provided evidence)."""
    if not run:
        return aggregate_intake(
            (),
            ready_label=ready_label,
            needs_feedback_label=needs_feedback_label,
            skip=True,
            skip_reason=skip_reason or "not_candidate",
        )
    shape = probe_repo_shape(clone_path)
    checks = (
        check_open(state=state),
        check_superseded(
            issue,
            merged_prs=merged_prs,
            closed_tracker_done=closed_tracker_done,
            tracker_refs=tracker_refs,
        ),
        check_duplicate_ai_pr(issue, covering_prs=covering_prs),
        check_shape(issue, shape),
        check_satisfied(issue, clone_path=clone_path),
        check_ambiguity(issue),
    )
    return aggregate_intake(
        checks,
        ready_label=ready_label,
        needs_feedback_label=needs_feedback_label,
        force_split=force_split,
    )
