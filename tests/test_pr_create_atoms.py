"""Contracts for minimal PR publication atoms."""


def test_head_issue_rewrites_stale_closing_link():
    from lokay.proc.prepare_pr_create_request import prepare

    out = prepare(
        repo="a/b",
        issue=6,
        title="x",
        body="Fixes #6",
        head="ai/fix/7-x",
        base="main",
        branch_prefix="ai/fix",
        live=False,
    )
    assert out["issue"] == 7 and "#7" in out["body"] and "#6" not in out["body"]


def test_issue_classifier_closes_missing_and_closed():
    from lokay.proc.classify_pr_create_issue import classify

    assert (
        classify({"route": "none"}, {"route": "classify", "issue_state": "MISSING"})[
            "reason"
        ]
        == "issue_closed"
    )
    assert (
        classify({"route": "none"}, {"route": "classify", "issue_state": "CLOSED"})[
            "route"
        ]
        == "terminal"
    )


def test_issue_classifier_allows_open_and_no_issue():
    from lokay.proc.classify_pr_create_issue import classify

    assert (
        classify({"route": "none"}, {"route": "classify", "issue_state": "OPEN"})[
            "route"
        ]
        == "create"
    )
    assert (
        classify({"route": "none"}, {"route": "open", "issue_state": None})["route"]
        == "create"
    )
