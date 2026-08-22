"""PR review evidence preserves the original ticket acceptance context."""

from pathlib import Path

from lokay.models import Issue
from lokay.pr_review import review_prompt
from lokay.prompts import pr_body


def _issue(body: str) -> Issue:
    return Issue(
        repo="mikolaj92/lokay",
        number=724,
        title="Implement bounded delivery",
        body=body,
        labels=["ai:ready"],
        assignees=["mikolaj92"],
        url="https://github.com/mikolaj92/lokay/issues/724",
        state="OPEN",
    )


def test_pr_body_carries_ticket_acceptance_evidence_into_review() -> None:
    acceptance = "Acceptance: fail closed when delivery evidence is unavailable."
    body = pr_body(_issue(acceptance), agent_summary="implemented")
    assert "## Ticket evidence" in body
    assert acceptance in body

    prompt = review_prompt(
        repo="mikolaj92/lokay",
        pr_number=724,
        title="fix",
        body=body,
        head_ref="ai/fix/724",
        diff_text="diff --git a/x b/x",
        checks_text="passed",
    )
    assert acceptance in prompt
    assert "PR body (includes the original ticket evidence):" in prompt


def test_pr_body_pins_ticket_review_semantics() -> None:
    import lokay.prompts as prompts

    source = Path(prompts.__file__).read_text(encoding="utf-8")
    assert "PR review receives the ticket body, not only the builder's summary." in source
