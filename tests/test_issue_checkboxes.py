"""Template Subsystem checkboxes are metadata, not work slices."""

from __future__ import annotations

from lokay.intake import check_ambiguity
from lokay.issue_checkboxes import (
    is_bug_issue,
    iter_work_checkboxes,
    work_checkbox_count,
)
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
    feature = _issue(title="Ship eight slices", body=body, labels=[])
    result = check_ambiguity(feature)
    assert result.verdict == "split"
    assert result.reason == "too_many_checkboxes"
    plan = plan_split(feature, reason="too_many_checkboxes")
    assert plan is not None
    assert plan.children[0].source == "checkbox"
    assert "deliverable" in plan.children[0].title


# Exact Temida `.github/ISSUE_TEMPLATE/bug_report.md` shape: bold labels, not ATX.
_TEMIDA_TEMPLATE = """**Describe the bug**
Nie mogę dać dokumentu do analizy. Job `argus-pilot-d556736a`.

**To Reproduce**
1. Otwórz portal
2. Wrzuć dokument
3. See error

**Expected behavior**
Analiza kończy się ready.

**Subsystem**
- [ ] Argus
- [ ] Dike
- [ ] Hermes
- [ ] Mnemozyna
- [ ] Posejdon
- [ ] Examples
- [ ] Other

**Environment (please complete the following information):**
- OS: macOS
- Python version: 3.12
- Commit/branch: main

**Additional context**
Jeden run_id, jeden symptom.
"""


def test_bold_subsystem_template_is_not_work():
    items = iter_work_checkboxes(_TEMIDA_TEMPLATE)
    assert items == []
    assert work_checkbox_count(_TEMIDA_TEMPLATE) == 0


def test_intake_does_not_split_bold_template_bug():
    issue = _issue(
        number=4671,
        title="[BUG] Nie mogę dać dokumentu do analizy",
        body=_TEMIDA_TEMPLATE,
        labels=["bug"],
    )
    result = check_ambiguity(issue)
    assert result.verdict != "split", result
    assert result.reason != "too_many_checkboxes"
    assert is_bug_issue(issue) is True
    assert plan_split(issue, reason="too_many_checkboxes") is None
    d = decide_issue(issue)
    assert d.decision != "split", d
    assert is_epic_like(issue) is False


def test_bug_with_many_work_boxes_stays_one_issue():
    body = "\n".join(f"- [ ] deliverable {i} with enough text" for i in range(8))
    issue = _issue(
        title="[BUG] One client symptom, eight acceptance boxes",
        body=body,
        labels=["bug"],
    )
    result = check_ambiguity(issue)
    assert result.verdict != "split"
    assert plan_split(issue, reason="too_many_checkboxes") is None
    d = decide_issue(_issue(title=issue.title, body=body, labels=["bug"]))
    assert d.decision != "split"
