from lokay.proc.classify_issue_row import CAP, CONTINUE, IDLE, classify, leftover_of


def test_empty_leftover_is_idle():
    out = classify({"result": {"leftover": 0, "leftover_issues": []}}, spent=0, budget=2)
    assert out["route"] == IDLE
    leftover, rows = leftover_of({"leftover": 0})
    assert leftover == 0 and rows == []


def test_skip_with_leftover_continues():
    out = classify(
        {
            "result": {
                "route": "skip",
                "leftover": 1,
                "leftover_issues": [{"repo": "o/r", "issue": 3}],
            }
        },
        spent=0,
        budget=1,
    )
    assert out["route"] == CONTINUE
    assert out["leftover"] == 1


def test_two_implementable_rows_continue_inside_budget():
    out = classify(
        {
            "result": {
                "route": "do",
                "launched": "started",
                "leftover": 1,
                "leftover_issues": [{"repo": "o/r", "issue": 3}],
            }
        },
        spent=1,
        budget=2,
    )
    assert out["route"] == CONTINUE


def test_spent_budget_is_cap():
    out = classify(
        {
            "result": {
                "route": "do",
                "launched": "started",
                "leftover": 1,
                "leftover_issues": [{"repo": "o/r", "issue": 3}],
            }
        },
        spent=1,
        budget=1,
    )
    assert out["route"] == CAP
    assert out["leftover"] == 1


def test_failed_live_receipt_with_empty_leftover_is_idle():
    out = classify(
        {
            "result": {
                "route": "failed",
                "launched": "failed",
                "leftover": 0,
                "leftover_issues": [],
            }
        },
        spent=0,
        budget=1,
    )
    assert out["route"] == IDLE
    assert out["leftover"] == 0


def test_failed_live_receipt_with_other_repos_continues():
    out = classify(
        {
            "result": {
                "route": "failed",
                "launched": "failed",
                "leftover": 1,
                "leftover_issues": [{"repo": "mikolaj92/Fala", "issue": 186}],
            }
        },
        spent=0,
        budget=1,
    )
    assert out["route"] == CONTINUE
    assert out["leftover"] == 1

