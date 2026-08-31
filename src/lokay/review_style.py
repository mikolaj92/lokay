"""Optional Kofte rendering for public PR-review prose."""

from __future__ import annotations

from collections.abc import Callable

from lokay.pr_review import PrReviewDecision, build_review_comment_body, format_review_marker

Stylist = Callable[[str, str], str]


def kofte_stylist(text: str, target: str) -> str:
    from kofte import Translator
    from kofte.llm import build_llm

    llm = build_llm()
    if llm is None:
        raise RuntimeError("Kofte LLM is not configured")
    return Translator(llm=llm).translate(text, source="en", target=target).text


def _human_text(decision: PrReviewDecision, *, escalated: bool) -> str:
    lines = [decision.summary or "(no summary)"]
    if escalated:
        lines.append(
            "Repeated request_changes reached the configured cap; human review is required."
        )
    if decision.blocking:
        lines.extend(["Blocking findings:", *(f"- {item}" for item in decision.blocking)])
    if decision.evidence_kind:
        lines.append(f"Evidence needed: {decision.evidence_kind}")
    if decision.nits:
        lines.extend(["Nits:", *(f"- {item}" for item in decision.nits)])
    return "\n".join(lines)


def style_review_comment(
    decision: PrReviewDecision,
    *,
    head_sha: str,
    merge_ok: bool,
    escalated: bool,
    target: str,
    stylist: Stylist = kofte_stylist,
) -> str:
    neutral = build_review_comment_body(
        decision, head_sha=head_sha, merge_ok=merge_ok, escalated=escalated
    )
    if not target.strip():
        return neutral
    try:
        styled = stylist(_human_text(decision, escalated=escalated), target.strip()).strip()
    except Exception:
        return neutral
    if not styled:
        return neutral
    marker = format_review_marker(
        head_sha=head_sha, verdict=decision.verdict, merge_ok=merge_ok
    )
    metadata = (
        f"scope_ok={decision.scope_ok} secrets={decision.secrets} "
        f"tests_adequate={decision.tests_adequate}"
    )
    return "\n".join(
        [
            marker,
            f"## Lokay LLM PR review: **{decision.verdict}** (risk={decision.risk})",
            "",
            styled,
            "",
            metadata,
            *( [f"head={head_sha}"] if head_sha else [] ),
        ]
    )
