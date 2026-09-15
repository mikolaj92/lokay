"""Structured LLM PR review — pure parse + decision helpers.

Fail-closed: invalid/missing JSON is never treated as approve.
"""

from __future__ import annotations

import json
from lokay.prompts import _clip
from lokay.tool_contracts import render_contract
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Verdict = Literal["approve", "request_changes", "needs_evidence", "fail_closed"]
Risk = Literal["low", "medium", "high"]
EvidenceKind = Literal["pr_metadata", "changed_files", "diff_tail", "commit_summary"]

VALID_VERDICTS = frozenset({"approve", "request_changes", "needs_evidence", "fail_closed"})
VALID_RISKS = frozenset({"low", "medium", "high"})
VALID_EVIDENCE_KINDS = frozenset({"pr_metadata", "changed_files", "diff_tail", "commit_summary"})
COLLECTOR_BOUNDARY = (
    "Collector boundary: a collector change may install/start durable background "
    "work after merge, but this PR must not use Pi or the lokay to populate data "
    "or wait for collection to finish."
)


@dataclass(frozen=True)
class PrReviewDecision:
    verdict: Verdict
    risk: Risk = "medium"
    scope_ok: bool = True
    secrets: bool = False
    tests_adequate: bool = True
    blocking: tuple[str, ...] = ()
    evidence_kind: EvidenceKind | None = None
    nits: tuple[str, ...] = ()
    summary: str = ""
    findings: tuple[dict[str, Any], ...] = ()
    reviewed_head_sha: str = ""
    task: dict[str, Any] = field(default_factory=dict)
    task_identity_sha256: str = ""
    review_result_sha256: str = ""
    review_input_fingerprint_sha256: str = ""
    review_preview_sha256: str = ""
    review_rule_config_sha256: str = ""
    review_runtime_config_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PrReviewError(ValueError):
    """Invalid structured review payload (fail closed)."""


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def extract_json_object(text: str) -> dict[str, Any]:
    """Pull the first JSON object from agent stdout. Fail closed."""
    raw = (text or "").strip()
    if not raw:
        raise PrReviewError("empty agent output")

    m = _JSON_FENCE.search(raw)
    if m:
        raw = m.group(1).strip()

    # Prefer first balanced {...}
    start = raw.find("{")
    if start < 0:
        raise PrReviewError("no JSON object in agent output")
    dec = json.JSONDecoder()
    try:
        obj, _end = dec.raw_decode(raw, start)
    except json.JSONDecodeError as exc:
        raise PrReviewError(f"invalid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise PrReviewError("JSON root must be an object")
    return obj


def decision_from_dict(data: dict[str, Any]) -> PrReviewDecision:
    allowed = {"verdict", "risk", "scope_ok", "secrets", "tests_adequate", "blocking", "evidence_kind", "nits", "summary", "findings", "reviewed_head_sha", "task", "task_identity_sha256", "review_result_sha256"}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise PrReviewError(f"unknown review fields: {unknown}")
    verdict = str(data.get("verdict") or "").strip().lower()
    if verdict not in VALID_VERDICTS:
        raise PrReviewError(
            f"verdict must be one of {sorted(VALID_VERDICTS)}, got {verdict!r}"
        )
    risk = str(data.get("risk") or "medium").strip().lower()
    if risk not in VALID_RISKS:
        risk = "medium"

    def _bool(key: str, default: bool) -> bool:
        if key not in data:
            return default
        value = data[key]
        if not isinstance(value, bool):
            raise PrReviewError(f"{key} must be a boolean")
        return value

    def _str_list(key: str) -> tuple[str, ...]:
        val = data.get(key) or []
        if not isinstance(val, list):
            raise PrReviewError(f"{key} must be a list")
        return tuple(str(x) for x in val if str(x).strip())

    summary = str(data.get("summary") or "").strip()
    evidence_kind = str(data.get("evidence_kind") or "").strip() or None
    if evidence_kind is not None and evidence_kind not in VALID_EVIDENCE_KINDS:
        raise PrReviewError(f"evidence_kind must be one of {sorted(VALID_EVIDENCE_KINDS)} or null")
    if verdict == "needs_evidence" and evidence_kind is None:
        raise PrReviewError("needs_evidence requires one evidence_kind")
    if verdict != "needs_evidence" and evidence_kind is not None:
        raise PrReviewError("evidence_kind is only valid with needs_evidence")
    return PrReviewDecision(
        verdict=verdict,  # type: ignore[arg-type]
        risk=risk,  # type: ignore[arg-type]
        scope_ok=_bool("scope_ok", True),
        secrets=_bool("secrets", False),
        tests_adequate=_bool("tests_adequate", True),
        blocking=_str_list("blocking"),
        evidence_kind=evidence_kind,  # type: ignore[arg-type]
        nits=_str_list("nits"),
        summary=summary,
        findings=tuple(dict(item) for item in data.get("findings", []) if isinstance(item, dict)),
        reviewed_head_sha=str(data.get("reviewed_head_sha") or ""),
        task=dict(data.get("task") or {}),
        task_identity_sha256=str(data.get("task_identity_sha256") or ""),
        review_result_sha256=str(data.get("review_result_sha256") or ""),
    )


def parse_review_output(text: str) -> PrReviewDecision:
    return decision_from_dict(extract_json_object(text))


def should_merge(decision: PrReviewDecision) -> bool:
    """Merge only on an explicit, internally consistent approval."""
    if decision.verdict != "approve":
        return False
    if decision.secrets or decision.blocking or decision.evidence_kind:
        return False
    if not decision.scope_ok or not decision.tests_adequate:
        return False
    return True


def should_repair(decision: PrReviewDecision) -> bool:
    """Only ordinary actionable findings may be delegated back to the coder."""
    return decision.verdict == "request_changes" and not decision.secrets


def is_soft_nits_only(decision: PrReviewDecision) -> bool:
    """True when findings are non-blocking nits only (docs/style), not product/security."""
    if decision.secrets or decision.blocking:
        return False
    if not decision.scope_ok or not decision.tests_adequate:
        return False
    if not decision.nits:
        return False
    return decision.verdict in {"approve", "request_changes", "fail_closed"}


def coerce_soft_nits(decision: PrReviewDecision) -> PrReviewDecision:
    """Documentation/style-only nits must not park PRs for humans or thrash repair.

    Keep ``fail_closed`` for product/security judgment and ``request_changes`` for
    real blocking work. Soft nits alone become ``approve`` (nits preserved).
    """
    if not is_soft_nits_only(decision):
        return decision
    if decision.verdict == "approve":
        return decision
    # fail_closed with only soft nits: only coerce low-risk (product/high stays human).
    if decision.verdict == "fail_closed" and decision.risk != "low":
        return decision
    return PrReviewDecision(
        verdict="approve",
        risk=decision.risk,
        scope_ok=decision.scope_ok,
        secrets=False,
        tests_adequate=decision.tests_adequate,
        blocking=(),
        evidence_kind=decision.evidence_kind,
        nits=decision.nits,
        summary=decision.summary or "soft nits only; approve",
        findings=decision.findings,
        reviewed_head_sha=decision.reviewed_head_sha,
        task=decision.task,
        task_identity_sha256=decision.task_identity_sha256,
        review_result_sha256=decision.review_result_sha256,
        review_input_fingerprint_sha256=decision.review_input_fingerprint_sha256,
        review_preview_sha256=decision.review_preview_sha256,
        review_rule_config_sha256=decision.review_rule_config_sha256,
        review_runtime_config_sha256=decision.review_runtime_config_sha256,
    )


def should_label_needs_review(
    decision: PrReviewDecision, *, escalated: bool = False
) -> bool:
    """``ai:needs-review`` only for secrets, product/human, or request_changes cap."""
    if escalated or decision.secrets:
        return True
    return decision.verdict == "fail_closed"


def labels_for_review(
    decision: PrReviewDecision, *, escalated: bool = False
) -> list[str]:
    labels: list[str] = []
    if should_label_needs_review(decision, escalated=escalated):
        labels.append("ai:needs-review")
    if decision.verdict == "request_changes" and not escalated:
        labels.append("ai:request-changes")
    return labels


def decide_review_merge(
    decision: PrReviewDecision,
    prior_request_changes: int,
    *,
    max_request_changes: int,
) -> tuple[bool, bool]:
    """Return ``(merge_ok, escalated)``. Cap fail-closes; never auto-merge."""
    merge_ok = should_merge(decision)
    escalated = (
        decision.verdict == "request_changes"
        and not decision.secrets
        and should_escalate_request_changes(
            prior_request_changes, max_request_changes=max_request_changes
        )
    )
    if escalated:
        merge_ok = False
    return merge_ok, escalated


# Durable marker embedded in published PR review comments.
# Used for head-SHA idempotency and request_changes escalation counts.
REVIEW_MARKER_RE = re.compile(
    r"<!--\s*lokay-review\s+head=(?P<head>[0-9a-fA-F]{40})\s+"
    r"verdict=(?P<verdict>[a-z_]+)\s+merge_ok=(?P<merge_ok>[01])"
    r"(?:\s+result=(?P<result>[a-f0-9]{64})\s+artifact=(?P<artifact>[a-f0-9]{64}))?\s*-->"
)


def format_review_marker(
    *, head_sha: str, verdict: str, merge_ok: bool,
    result_sha256: str = "", artifact_sha256: str = "",
) -> str:
    sha = (head_sha or "").strip().lower()
    verd = (verdict or "").strip().lower() or "fail_closed"
    if not re.fullmatch(r"[a-f0-9]{40}", sha) or not re.fullmatch(r"[a-z_]+", verd):
        raise ValueError("review marker identity is malformed")
    suffix = ""
    if result_sha256 or artifact_sha256:
        if not re.fullmatch(r"[a-f0-9]{64}", result_sha256) or not re.fullmatch(r"[a-f0-9]{64}", artifact_sha256):
            raise ValueError("review marker artifact identity is malformed")
        suffix = f" result={result_sha256} artifact={artifact_sha256}"
    return f"<!-- lokay-review head={sha} verdict={verd} merge_ok={1 if merge_ok else 0}{suffix} -->"


def parse_review_markers(comment_bodies: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    """Extract lokay-review markers from PR comment bodies (oldest → newest)."""
    out: list[dict[str, Any]] = []
    for body in comment_bodies or []:
        if not isinstance(body, str):
            continue
        for match in REVIEW_MARKER_RE.finditer(body):
            verd = match.group("verdict").strip().lower()
            out.append(
                {
                    "head_sha": match.group("head").strip().lower(),
                    "verdict": verd,
                    "merge_ok": match.group("merge_ok") == "1",
                    "result_sha256": str(match.group("result") or ""),
                    "artifact_sha256": str(match.group("artifact") or ""),
                }
            )
    return out


def find_review_for_head(
    markers: list[dict[str, Any]], head_sha: str
) -> dict[str, Any] | None:
    """Return the newest marker for this head SHA, if any."""
    want = (head_sha or "").strip().lower()
    if not want:
        return None
    for marker in reversed(markers):
        if str(marker.get("head_sha") or "") == want:
            return marker
    return None


def count_request_changes_reviews(markers: list[dict[str, Any]]) -> int:
    return len({
        str(marker.get("head_sha") or "").lower()
        for marker in markers
        if marker.get("verdict") == "request_changes" and marker.get("head_sha")
    })


def should_escalate_request_changes(
    prior_request_changes: int, *, max_request_changes: int
) -> bool:
    """True when earlier published request_changes already exhausted the repair cap."""
    limit = max(1, int(max_request_changes))
    return int(prior_request_changes) >= limit


def build_review_comment_body(
    decision: PrReviewDecision,
    *,
    head_sha: str,
    merge_ok: bool,
    escalated: bool = False,
) -> str:
    lines = [
        format_review_marker(
            head_sha=head_sha, verdict=decision.verdict, merge_ok=merge_ok
        ),
        f"## Lokay LLM PR review: **{decision.verdict}** (risk={decision.risk})",
        "",
        decision.summary or "(no summary)",
        "",
    ]
    if escalated:
        lines.extend(
            [
                "### Escalation",
                "- Repeated `request_changes` reached the configured cap; "
                "labeled `ai:needs-review` and stopped auto repair/re-review.",
                "",
            ]
        )
    if decision.blocking:
        lines.append("### Blocking")
        lines.extend(f"- {b}" for b in decision.blocking)
        lines.append("")
    if decision.evidence_kind:
        lines.append("### Evidence needed")
        lines.append(f"- {decision.evidence_kind}")
        lines.append("")
    if decision.nits:
        lines.append("### Nits")
        lines.extend(f"- {n}" for n in decision.nits)
        lines.append("")
    lines.append(
        f"scope_ok={decision.scope_ok} secrets={decision.secrets} "
        f"tests_adequate={decision.tests_adequate}"
    )
    if head_sha:
        lines.append(f"head={head_sha}")
    return "\n".join(lines)


_APPROACH_REL = ".lokay/approach.md"


def strip_approach_from_diff(diff_text: str) -> str:
    """Drop `.lokay/approach.md` hunks so the reviewer never sees the builder plan."""
    text = diff_text or ""
    if _APPROACH_REL not in text:
        return text
    kept: list[str] = []
    skip = False
    for line in text.splitlines(keepends=True):
        if line.startswith("diff --git"):
            skip = _APPROACH_REL in line
        if skip:
            continue
        kept.append(line)
    return "".join(kept)


def review_prompt(
    *,
    repo: str,
    pr_number: int,
    title: str,
    body: str,
    head_ref: str,
    diff_text: str,
    checks_text: str,
    contract: str = "pr_review",
    extra_values: dict[str, str] | None = None,
) -> str:
    reviewer_diff = strip_approach_from_diff(diff_text or "")
    schema = """{
  "verdict": "approve" | "request_changes" | "needs_evidence" | "fail_closed",
  "risk": "low" | "medium" | "high",
  "scope_ok": boolean,
  "secrets": boolean,
  "tests_adequate": boolean,
  "blocking": ["..."],
  "evidence_kind": "pr_metadata" | "changed_files" | "diff_tail" | "commit_summary" | null,
  "nits": ["..."],
  "summary": "one short paragraph"
}"""
    values = {
        "repo": repo,
        "pr_number": pr_number,
        "head_ref": head_ref,
        "schema": schema,
        "collector_boundary": COLLECTOR_BOUNDARY,
        "checks_text": _clip(checks_text or "(none)", 4000),
        "title": title,
        "body": _clip(body or "", 12000),
        "diff_text": _clip(reviewer_diff or "(no diff)", 12000),
    }
    values.update(extra_values or {})
    return render_contract(contract, **values)
