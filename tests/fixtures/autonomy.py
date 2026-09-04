"""Hermetic helpers for autonomy certainty contracts.

Keep tick/lokay wiring out of product code: these fixtures only build configs
and stub envelopes for pytest. No network, no gh mutation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping


def write_lokay_config(
    tmp_path: Path,
    *,
    repos: Iterable[str] = ("a/one", "a/two"),
    mode: str = "live",
    executor_enabled: bool = True,
    merge_enabled: bool = True,
    require_checks: bool = False,
    require_llm_review: bool = True,
    max_issue_to_pr_per_pass: int = 1,
    max_triage_per_tick: int = 0,
    max_repairs_per_tick: int = 0,
    name: str = "config.yaml",
) -> str:
    """Write a minimal lokay config under tmp_path; return its path string."""
    path = tmp_path / name
    rows = "\n".join(
        f"  - name: {repo}\n    clone_path: {tmp_path}" for repo in repos
    )
    path.write_text(
        f"""mode: {mode}
repos:
{rows}
executor:
  enabled: {str(executor_enabled).lower()}
  agent: pi
  command: true
  args:
    - "{{prompt}}"
merge:
  enabled: {str(merge_enabled).lower()}
  require_checks: {str(require_checks).lower()}
  require_llm_review: {str(require_llm_review).lower()}
limits:
  max_triage_per_tick: {max_triage_per_tick}
  max_issue_to_pr_per_pass: {max_issue_to_pr_per_pass}
  max_repairs_per_tick: {max_repairs_per_tick}
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    return str(path)


def intake_ready_envelope(*, reason: str = "intake_ok") -> dict[str, Any]:
    return {
        "ok": True,
        "implementable": True,
        "applied": False,
        "decision": {"decision": "ready", "reason": reason},
    }


def intake_reject_envelope(
    decision: str,
    *,
    reason: str,
    applied: bool = True,
) -> dict[str, Any]:
    """CLOSE / SPLIT / NEEDS_HUMAN — never implementable under --require-ready."""
    return {
        "ok": True,
        "implementable": False,
        "applied": applied,
        "decision": {"decision": decision, "reason": reason},
        "reason": reason,
    }


def open_ai_pr(
    number: int = 1,
    *,
    labels: list[str] | None = None,
) -> dict[str, Any]:
    pr: dict[str, Any] = {
        "number": number,
        "head_ref": f"ai/fix/{number}-x",
        "mergeable": "MERGEABLE",
    }
    if labels is not None:
        pr["labels"] = labels
    return pr


def review_envelope(
    verdict: str,
    *,
    merge_ok: bool | None = None,
    secrets: bool = False,
    escalated: bool = False,
    skipped: bool = False,
    reason: str = "",
) -> dict[str, Any]:
    if merge_ok is None:
        merge_ok = verdict == "approve" and not secrets and not escalated
    out: dict[str, Any] = {
        "merge_ok": merge_ok,
        "decision": {
            "verdict": verdict,
            "secrets": secrets,
            "blocking": [],
            "nits": [],
            "scope_ok": True,
            "tests_adequate": True,
        },
        "escalated": escalated,
    }
    if skipped:
        out["skipped"] = True
    if reason:
        out["reason"] = reason
    return out


def assert_no_live_gh(argv: list[str]) -> None:
    """Guard: contract stubs must not look like live network gh invocations."""
    joined = " ".join(argv)
    assert "api.github.com" not in joined
    assert "--hostname" not in argv


def step_names(actions: Iterable[Mapping[str, Any]]) -> list[str]:
    return [str(a.get("step") or "") for a in actions if isinstance(a, Mapping)]
