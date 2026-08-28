from lokay.proc.select_issue_do import select as select_do
from lokay.proc.select_next_issue import select
from lokay.proc.walk_issue_leftover import consumes, keep, product_first, queue


def _ready(issue: int) -> dict:
    return {
        "repo": "Temida/Temida",
        "issue": issue,
        "title": f"temida-{issue}",
        "labels": ["ai:ready", "work:ready"],
    }


def test_sito_not_ready_keeps_three_ready_temida_and_does():
    leftover = [_ready(5001), _ready(4999), _ready(4997)]
    listed = {"issues": leftover, "count": 3, "overflow": False}
    last = {"leftover": 3, "leftover_issues": leftover}
    picked = select(listed, last=last)
    assert picked["route"] == "issue"
    assert picked["repo"] == "Temida/Temida"
    assert picked["issue"] == 5001
    assert picked["leftover"] == 2
    do = select_do(picked, {"route": "failed", "error": "triage_not_done"}, listed)
    assert do["ok"] is True
    assert do["route"] == "do"
    assert do["issue"] == 5001
    assert do["leftover"] == 3
    assert [row["issue"] for row in do["leftover_issues"]] == [5001, 4999, 4997]
    again = select(listed, last=do)
    assert again["issue"] == 5001
    assert again["leftover"] == 2


def test_sito_nie_robic_keeps_three_ready_and_first_is_do():
    leftover = [_ready(5001), _ready(4999), _ready(4997)]
    listed = {"issues": leftover, "count": 3}
    picked = select(listed)
    do = select_do(
        picked,
        {"route": "completed", "triage": {"result": {"implementable": False}}},
        listed,
    )
    assert do["route"] == "do"
    assert do["issue"] == 5001
    assert do["leftover"] == 3
    assert [row["issue"] for row in do["leftover_issues"]] == [5001, 4999, 4997]


def test_adapter_fail_keeps_leftover_and_ready_does():
    leftover = [_ready(4996)]
    listed = {"issues": leftover, "count": 1}
    picked = select(listed)
    do = select_do(
        picked,
        {"route": "failed", "error": "adapter_failed"},
        listed,
    )
    assert do["route"] == "do"
    assert do["leftover"] == 1
    assert do["leftover_issues"][0]["issue"] == 4996


def test_keep_starts_at_the_pick():
    rows = [_ready(5001), _ready(4999), _ready(4997)]
    assert [row["issue"] for row in keep(rows, rows[0])] == [5001, 4999, 4997]


def test_oil_yields_to_product_in_queue():
    listed = [
        {"repo": "mikolaj92/lokay", "issue": 848, "title": "oil"},
        _ready(5001),
    ]
    last = {
        "leftover_issues": [
            {"repo": "mikolaj92/lokay", "issue": 848},
            {"repo": "Temida/Temida", "issue": 5001},
        ]
    }
    out = queue(listed, last)
    assert [row["issue"] for row in out] == [5001]
    assert product_first(listed)[0]["issue"] == 5001


def test_queue_drops_foreign_assignee():
    listed = [
        {"repo": "Temida/Temida", "issue": 1, "assignees": []},
        {"repo": "Temida/Temida", "issue": 2, "assignees": ["mikolaj92"]},
        {"repo": "Temida/Temida", "issue": 3, "assignees": ["PSyron"]},
    ]
    out = queue(listed, None, mill="mikolaj92")
    assert [row["issue"] for row in out] == [1, 2]


def test_consumes_only_authored_skip():
    assert consumes("needs_human")
    assert consumes("blocked")
    assert consumes("already-closed")
    assert not consumes("triage_not_done")
    assert not consumes("sito_nie_robic")
    assert not consumes("adapter_failed")
