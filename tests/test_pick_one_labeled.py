from lokay.proc.pick_one_labeled import pick_one_labeled


def test_picks_the_first_labeled_issue():
    issues = [
        {"number": 1, "labels": []},
        {"number": 2, "labels": ["ai:ready"]},
        {"number": 3, "labels": ["ready-for-agent"]},
    ]
    out = pick_one_labeled(issues)
    assert out == {"ok": True, "issue": issues[1], "reason": "picked"}


def test_unlabeled_issues_are_not_a_pick():
    out = pick_one_labeled([{"number": 1, "labels": ["bug"]}])
    assert out == {"ok": True, "issue": None, "reason": "none_ready"}


def test_an_occupied_labeled_issue_blocks_the_repo():
    issues = [
        {"number": 2, "labels": ["ai:ready"]},
        {"number": 3, "labels": ["ai:ready"]},
    ]
    out = pick_one_labeled(issues, occupied={2})
    assert out == {"ok": True, "issue": None, "reason": "occupied"}
