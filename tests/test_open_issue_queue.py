"""Open catalog issue is the queue. Lokay labels are not a gate."""

from pathlib import Path

from lokay.proc.pass_lane import classify_pass_lane, product_candidates
from lokay.proc.survey_ttl import lokay_survey_still_empty
from lokay.triage import is_human_stopped, is_open_work_issue


def test_unlabeled_is_open_work_and_human_stops_are_not() -> None:
    assert is_open_work_issue([]) is True
    assert is_open_work_issue(["ai:ready"]) is True
    assert is_open_work_issue(["work:ready"]) is True
    assert is_open_work_issue(["ai:blocked"]) is False
    assert is_open_work_issue(["ai:needs-feedback"]) is False
    assert is_open_work_issue(["frozen"]) is False
    assert is_open_work_issue(["ai:tracker"]) is False
    assert is_human_stopped(["ai:blocked"]) is True


def test_inbox_only_unlabeled_product_is_catalog_work() -> None:
    from lokay.proc.catalog_work import remaining_ready_count, work_by_repo

    work = work_by_repo(
        {
            "ready_by_repo": {},
            "inbox_issues_by_repo": {
                "mikolaj92/Temida": [{"number": 4968, "labels": []}]
            },
        }
    )
    assert remaining_ready_count(work) == 1
    assert (
        product_candidates(ready_by_repo=work, self_id="mikolaj92/lokay") is True
    )
    assert (
        classify_pass_lane(self_id="mikolaj92/lokay", ready_by_repo=work)
        == "product"
    )


def test_inbox_human_stop_and_covering_pr_are_not_work() -> None:
    from lokay.proc.catalog_work import remaining_ready_count, work_by_repo

    work = work_by_repo(
        {
            "ready_by_repo": {},
            "inbox_issues_by_repo": {
                "mikolaj92/Temida": [
                    {"number": 1, "labels": ["ai:blocked"]},
                    {"number": 2, "labels": []},
                ]
            },
            "prs_by_repo": {
                "mikolaj92/Temida": [{"head_ref": "ai/fix/2-x"}]
            },
        }
    )
    assert remaining_ready_count(work) == 0


def test_unlabeled_product_issue_yields_product_lane() -> None:
    ready = {"mikolaj92/Temida": [{"number": 4968, "labels": []}]}
    assert (
        product_candidates(ready_by_repo=ready, self_id="mikolaj92/lokay") is True
    )
    assert (
        classify_pass_lane(self_id="mikolaj92/lokay", ready_by_repo=ready) == "product"
    )


def test_only_human_stops_are_not_product() -> None:
    ready = {
        "mikolaj92/Temida": [
            {"number": 1, "labels": ["ai:blocked"]},
            {"number": 2, "labels": ["ai:needs-feedback"]},
            {"number": 3, "labels": ["frozen"]},
        ]
    }
    kept = {
        repo: [row for row in rows if is_open_work_issue(row.get("labels") or [])]
        for repo, rows in ready.items()
    }
    assert product_candidates(ready_by_repo=kept, self_id="mikolaj92/lokay") is False
    assert classify_pass_lane(self_id="mikolaj92/lokay", ready_by_repo=kept) == "idle"


def test_empty_catalog_is_idle() -> None:
    assert classify_pass_lane(self_id="mikolaj92/lokay") == "idle"


def test_unlabeled_self_issue_empty_product_is_oil() -> None:
    self_id = "mikolaj92/lokay"
    ready = {self_id: [{"number": 786, "labels": []}]}
    assert product_candidates(ready_by_repo=ready, self_id=self_id) is False
    assert classify_pass_lane(self_id=self_id, ready_by_repo=ready) == "oil"


def _gh_ok(stdout: str):
    return type("R", (), {"returncode": 0, "stdout": stdout, "stderr": ""})()


def test_idle_probe_unlabeled_product_issue_is_not_empty() -> None:
    def fake_run(argv, **_k):
        if "issue" in argv:
            return _gh_ok('[{"number": 4968, "state": "OPEN", "labels": []}]')
        return _gh_ok("[]")

    assert (
        lokay_survey_still_empty(repo="mikolaj92/Temida", run=fake_run) is False
    )


def test_idle_probe_only_human_stops_is_empty() -> None:
    def fake_run(argv, **_k):
        if "issue" in argv:
            return _gh_ok(
                '[{"number":1,"state":"OPEN","labels":[{"name":"ai:blocked"}]},'
                '{"number":2,"state":"OPEN","labels":[{"name":"ai:needs-feedback"}]}]'
            )
        return _gh_ok("[]")

    assert lokay_survey_still_empty(repo="mikolaj92/Temida", run=fake_run) is True


def test_list_work_ready_does_not_require_work_ready_label(monkeypatch) -> None:
    from lokay.proc import list_work_ready_issues

    seen: list[list[str]] = []

    def fake(main, argv):
        seen.append(list(argv))
        return {"ok": True, "issues": [{"number": 4968, "labels": []}]}

    monkeypatch.setattr(list_work_ready_issues, "run_proc", fake)
    out = list_work_ready_issues.fetch(
        {"repo": "mikolaj92/Temida"}, config_path=None, live=True
    )
    assert out["route"] == "listed"
    assert "--label" not in seen[0]
    assert "work:ready" not in seen[0]


def test_docs_do_not_say_the_queue_is_work_ready() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden = (
        "list implementable `work:ready`",
        "product `work:ready`",
        "inbox, `work:ready` (with `ai:ready`)",
        "Listing `work:ready` jest fizycznym odczytem",
    )
    for rel in ("README.md", "docs/GRAPH.md", "AGENTS.md", "docs/WORKING.md"):
        text = (root / rel).read_text(encoding="utf-8")
        for phrase in forbidden:
            assert phrase not in text, f"{rel} still says {phrase!r}"
    list_atom = (
        root / "src" / "lokay" / "proc" / "list_work_ready_issues.py"
    ).read_text(encoding="utf-8")
    assert "--label" not in list_atom
    assert "work:ready" not in list_atom
    ttl = (root / "src" / "lokay" / "proc" / "survey_ttl.py").read_text(encoding="utf-8")
    assert "LABEL_WORK_READY" not in ttl
    assert '"--label"' not in ttl
