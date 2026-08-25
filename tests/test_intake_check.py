"""Contracts for minimal authored mechanical intake check."""


def test_foreign_repo_is_explicit_skip():
    from lokay.proc.prepare_intake_check import prepare

    out = prepare(
        repo="a/b",
        issue=7,
        check="open",
        merged_prs=[],
        tracker_done=False,
        covering_prs=[],
        live=False,
    )
    assert out["route"] == "terminal" and out["reason"] == "repo_not_intake_target"


def test_covering_pr_parser_is_closed_and_bounded():
    from lokay.proc.parse_intake_covering_prs import parse

    out = parse({"covering_prs": ["7:merged", "8:open"]})
    assert out["route"] == "parsed" and out["prs"] == [
        {"number": 7, "state": "MERGED", "merged": True},
        {"number": 8, "state": "OPEN", "merged": False},
    ]


def test_selector_requires_exactly_one_branch():
    from lokay.proc.select_intake_check_result import select

    good = {"route": "selected", "check": {"verdict": "pass"}}
    assert select({}, good, {}) == good and select(good, good)["route"] == "terminal"
