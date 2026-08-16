"""Template Subsystem checkboxes are metadata, not work slices."""

from __future__ import annotations

from lokay.intake import check_ambiguity
from lokay.issue_checkboxes import iter_work_checkboxes, work_checkbox_count
from lokay.models import Issue
from lokay.queue_conflict import is_epic_like
from lokay.split import plan_split
from lokay.triage import decide_issue

# Shape of Temida#4710 / #4671: one bug + product-routing form + Done means.
_BUG_4710 = """## Describe the bug

Analiza dokumentu w portalu klienta kończy się błędem technicznym zamiast
gotowej pary DOCX. Job `argus-pilot-20260816T064738-c8c9af8f`.

## Expected behavior

1. Analiza kończy się statusem `ready` i parą DOCX.
2. Fail-closed daje konkretny powód, nie goły błąd techniczny.

## Subsystem

- [x] Argus
- [x] Dike
- [ ] Hermes
- [ ] Mnemozyna
- [ ] Posejdon
- [ ] Examples
- [ ] Other

## Environment

- Surface: Argus client portal
- Host: argus.patryk.it

## Done means

- [ ] Zdiagnozowany root cause dla tego run_id
- [ ] Naprawiony path analizy / adaptera / timeoutu, jeśli to awaria
- [ ] Klient nie dostaje gołego błędu technicznego bez akcji
- [ ] Test regresyjny na projekcję client failure
- [ ] Potwierdzenie na hoście, że nowy run kończy się ready albo czytelnym fail

## Out of scope

- redesign całego client portal UX
- fixy w hermes/mnemozyna, o ile dead-letter nie wskaże ich
"""


def _issue(**kwargs) -> Issue:
    base = dict(
        repo="mikolaj92/Temida",
        number=4710,
        title="[BUG] Analiza dokumentu pada na chwilowy błąd techniczny",
        body=_BUG_4710,
        labels=["bug"],
        assignees=["mikolaj92"],
        url="https://github.com/mikolaj92/Temida/issues/4710",
        state="OPEN",
    )
    base.update(kwargs)
    return Issue(**base)


def test_subsystem_tags_are_not_work_checkboxes():
    items = iter_work_checkboxes(_BUG_4710)
    assert "Argus" not in items
    assert "Dike" not in items
    assert work_checkbox_count(_BUG_4710) == 5
    assert any("root cause" in x for x in items)


def test_intake_does_not_split_template_bug_as_epic():
    result = check_ambiguity(_issue())
    assert result.verdict != "split", result
    assert result.reason != "too_many_checkboxes"


def test_triage_does_not_split_template_bug():
    d = decide_issue(_issue(labels=[]))
    assert d.decision != "split", d
    assert d.reason != "too_large_split"


def test_split_plan_does_not_mint_product_name_children():
    plan = plan_split(_issue(), reason="too_many_checkboxes")
    if plan is None:
        return
    titles = {c.title for c in plan.children}
    assert "Argus" not in titles
    assert "Dike" not in titles
    assert "Hermes" not in titles


def test_queue_conflict_template_bug_is_not_epic_like():
    assert is_epic_like(_issue()) is False


def test_real_work_checkboxes_still_split():
    body = "\n".join(f"- [ ] deliverable {i} with enough text" for i in range(8))
    result = check_ambiguity(_issue(title="Ship eight slices", body=body, labels=[]))
    assert result.verdict == "split"
    assert result.reason == "too_many_checkboxes"
    plan = plan_split(_issue(body=body), reason="too_many_checkboxes")
    assert plan is not None
    assert plan.children[0].source == "checkbox"
    assert "deliverable" in plan.children[0].title
