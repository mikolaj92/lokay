"""Survey lists must not silently drop oldest tickets behind a newest-first cap."""

from __future__ import annotations

import json

import pytest

from lokay.config import Config, RepoConfig
from lokay.gh_issues import list_inbox_issues, list_issues_with_label, list_ready_issues
from lokay.gh_prs import list_open_ai_prs
from lokay.envelope import emit_exit, ok
from lokay.gh_rate import SURVEY_LIST_CAP, parse_survey_list, survey_list_cap
from lokay.passkit import io as pass_io
from lokay.proc import survey_ready
from lokay.runner import CommandResult, CommandSpec


class _ListRunner:
    def __init__(self, rows: list[dict] | dict, *, returncode: int = 0) -> None:
        self.rows = rows
        self.returncode = returncode
        self.calls: list[tuple[str, ...]] = []

    def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        self.calls.append(spec.argv)
        payload = self.rows
        if isinstance(self.rows, dict):
            argv = list(spec.argv)
            kind = "issue" if "issue" in argv else "pr"
            payload = self.rows.get(kind, [])
        return CommandResult(
            spec=spec,
            executed=live,
            returncode=self.returncode,
            stdout=json.dumps(payload) if self.returncode == 0 else "",
        )

    def run_checked(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        result = self.run(spec, live=live)
        if live and result.returncode != 0:
            raise RuntimeError("fail")
        return result


def _cfg(tmp_path) -> tuple[Config, RepoConfig]:
    repo = RepoConfig(name="mikolaj92/influenzer", clone_path=tmp_path)
    cfg = Config(
        assignee="mikolaj92",
        allow_unassigned=True,
        repos=[repo],
        ready_label="ai:ready",
        blocked_label="ai:blocked",
        branch_prefix="ai/fix",
    )
    return cfg, repo


def _issue_row(number: int, *labels: str, state: str = "OPEN") -> dict:
    return {
        "number": number,
        "title": f"issue {number}",
        "body": "body",
        "labels": [{"name": name} for name in labels],
        "assignees": [{"login": "mikolaj92"}],
        "author": {"login": "mikolaj92"},
        "url": f"https://example.com/{number}",
        "state": state,
    }


def test_survey_list_cap_clamps_to_hard_ceiling():
    assert survey_list_cap() == SURVEY_LIST_CAP
    assert survey_list_cap(50) == 50
    assert survey_list_cap(5000) == SURVEY_LIST_CAP
    assert survey_list_cap(0) == 1


def test_parse_survey_list_refuses_a_full_newest_first_page():
    rows = parse_survey_list('[{"number": 1}]', kind="ready-issue", repo="a/b", cap=10)
    assert rows == [{"number": 1}]
    with pytest.raises(RuntimeError, match="newest-first cap"):
        parse_survey_list(
            json.dumps([{"number": i} for i in range(10)]),
            kind="ready-issue",
            repo="a/b",
            cap=10,
        )
    with pytest.raises(RuntimeError, match="non-list"):
        parse_survey_list("{}", kind="ready-issue", repo="a/b", cap=10)


def test_list_ready_asks_for_full_page_and_keeps_oldest(tmp_path):
    runner = _ListRunner(
        [
            _issue_row(185, "ai:ready"),
            _issue_row(45, "ai:ready"),
            _issue_row(24, "ai:ready"),
        ]
    )
    cfg, repo = _cfg(tmp_path)
    issues = list_ready_issues(runner, cfg, repo, live=True)
    assert [i.number for i in issues] == [185, 45, 24]
    argv = runner.calls[0]
    assert argv[argv.index("--limit") + 1] == str(SURVEY_LIST_CAP)
    assert "--label" in argv
    assert argv[argv.index("--label") + 1] == "ai:ready"
    assert argv[argv.index("--state") + 1] == "all"
    assert "state" in argv[argv.index("--json") + 1].split(",")


def test_list_ready_defaults_missing_state_to_open_and_excludes_closed(tmp_path):
    missing_state = _issue_row(8, "ai:ready")
    missing_state.pop("state")
    runner = _ListRunner(
        [
            missing_state,
            _issue_row(7, "ai:ready", state="closed"),
        ]
    )
    cfg, repo = _cfg(tmp_path)

    issues = list_ready_issues(runner, cfg, repo, live=True)

    assert [(issue.number, issue.state) for issue in issues] == [(8, "OPEN")]


def test_list_ready_fail_closed_when_page_is_full(tmp_path):
    runner = _ListRunner([_issue_row(i, "ai:ready") for i in range(SURVEY_LIST_CAP)])
    cfg, repo = _cfg(tmp_path)
    with pytest.raises(RuntimeError, match="newest-first cap"):
        list_ready_issues(runner, cfg, repo, live=True)


def test_list_inbox_uses_full_page(tmp_path):
    runner = _ListRunner([_issue_row(3), _issue_row(2, "ai:ready")])
    cfg, repo = _cfg(tmp_path)
    issues = list_inbox_issues(runner, cfg, repo, live=True)
    assert [i.number for i in issues] == [3]
    argv = runner.calls[0]
    assert argv[argv.index("--limit") + 1] == str(SURVEY_LIST_CAP)
    assert argv[argv.index("--state") + 1] == "open"


def test_list_inbox_skips_stuck_blocked_issue(tmp_path):
    (tmp_path / "stuck.json").write_text(
        json.dumps({"issues": {"mikolaj92/influenzer#3": {"blocked": True}}}),
        encoding="utf-8",
    )
    runner = _ListRunner([_issue_row(3), _issue_row(4)])
    cfg, repo = _cfg(tmp_path)
    cfg.state_path = tmp_path / "state.jsonl"

    issues = list_inbox_issues(runner, cfg, repo, live=True)

    assert [i.number for i in issues] == [4]


def test_list_issues_with_label_uses_full_page(tmp_path):
    runner = _ListRunner([_issue_row(9, "ai:needs-feedback")])
    cfg, repo = _cfg(tmp_path)
    issues = list_issues_with_label(
        runner, cfg, repo, label="ai:needs-feedback", live=True
    )
    assert [i.number for i in issues] == [9]
    argv = runner.calls[0]
    assert argv[argv.index("--limit") + 1] == str(SURVEY_LIST_CAP)
    assert argv[argv.index("--state") + 1] == "open"


def test_list_issues_with_ready_label_includes_closed_issues_for_closeout(tmp_path):
    runner = _ListRunner(
        [
            _issue_row(7, "ai:ready", state="CLOSED"),
            _issue_row(8, "ai:ready"),
        ]
    )
    cfg, repo = _cfg(tmp_path)

    issues = list_issues_with_label(runner, cfg, repo, label="ai:ready", live=True)

    assert [(issue.number, issue.state) for issue in issues] == [
        (7, "CLOSED"),
        (8, "OPEN"),
    ]
    argv = runner.calls[0]
    assert argv[argv.index("--state") + 1] == "all"
    assert "state" in argv[argv.index("--json") + 1].split(",")


def test_list_issues_with_work_ready_label_includes_closed_for_closeout(tmp_path):
    runner = _ListRunner(
        [
            _issue_row(7, "work:ready", state="CLOSED"),
            _issue_row(8, "work:ready", state=""),
        ]
    )
    cfg, repo = _cfg(tmp_path)

    issues = list_issues_with_label(runner, cfg, repo, label="work:ready", live=True)

    assert [(issue.number, issue.state) for issue in issues] == [
        (7, "CLOSED"),
        (8, "OPEN"),
    ]
    argv = runner.calls[0]
    assert argv[argv.index("--state") + 1] == "all"


def test_survey_ready_parks_blocked_ready_issue(tmp_path, monkeypatch):
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {"repos": ["owner/repo"], "branch_prefix": "ai/fix/"},
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {
            "actions": [],
            "progress": 0,
            "stuck": {"issues": {"owner/repo#7": {"blocked": True}}},
            "prs_by_repo": {},
        },
    )
    parked: list[list[str]] = []

    def fake_list(argv=None):
        return emit_exit(
            ok(
                repo="owner/repo",
                issues=[
                    {"number": 7, "labels": ["work:ready"]},
                    {"number": 8, "labels": ["work:ready"]},
                ],
            )
        )

    def fake_get(argv=None):
        return emit_exit(ok(issue={"state": "OPEN"}))

    def fake_park(argv=None):
        parked.append(list(argv or []))
        return emit_exit(ok(applied=True, removed=True))

    monkeypatch.setattr(survey_ready.p_list_issues, "main", fake_list)
    monkeypatch.setattr(survey_ready.p_get_issue, "main", fake_get)
    monkeypatch.setattr(survey_ready.p_park, "main", fake_park)

    result = survey_ready.run_survey_ready(
        pass_dir=str(pass_dir), config_path=None, live=True
    )

    assert result["ok"] is True
    assert parked == [["--repo", "owner/repo", "--issue", "7"]]
    survey = pass_io.read_json(pass_io.survey_path(pass_dir))
    assert [issue["number"] for issue in survey["ready_by_repo"]["owner/repo"]] == [8]
    assert survey["remaining_ready"] == 1
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert any(action["step"] == "park_stuck" for action in working["actions"])


def test_survey_ready_closes_out_delivered_closed_issue_without_i2pr(
    tmp_path, monkeypatch
):
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {"repos": ["owner/repo"], "branch_prefix": "ai/fix/"},
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {"actions": [], "progress": 0, "prs_by_repo": {}},
    )
    closed_out: list[list[str]] = []
    listed: list[list[str]] = []

    def fake_list(argv=None):
        listed.append(list(argv or []))
        return emit_exit(
            ok(
                issues=[
                    {"number": 7, "labels": ["work:ready"]},
                    {"number": 8, "labels": ["work:ready"]},
                ]
            )
        )

    def fake_get(argv=None):
        number = int((argv or [])[-1])
        return emit_exit(ok(issue={"state": "CLOSED" if number == 7 else "OPEN"}))

    def fake_closeout(argv=None):
        closed_out.append(list(argv or []))
        return emit_exit(ok(delivered=True, labels_removed=True))

    monkeypatch.setattr(survey_ready.p_list_issues, "main", fake_list)
    monkeypatch.setattr(survey_ready.p_get_issue, "main", fake_get)
    monkeypatch.setattr(survey_ready.p_closeout, "main", fake_closeout)

    result = survey_ready.run_survey_ready(
        pass_dir=str(pass_dir), config_path=None, live=True
    )

    assert result["ok"] is True
    assert listed == [["--live", "--repo", "owner/repo", "--label", "work:ready"]]
    assert closed_out == [["--live", "--repo", "owner/repo", "--issue", "7"]]
    survey = pass_io.read_json(pass_io.survey_path(pass_dir))
    assert [issue["number"] for issue in survey["ready_by_repo"]["owner/repo"]] == [8]
    assert survey["remaining_ready"] == 1
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["progress"] == 1
    assert int(working.get("issue_to_pr_started") or 0) == 0
    assert any(
        action["step"] == "closeout_closed_ready" for action in working["actions"]
    )


def test_list_open_ai_prs_uses_full_page(tmp_path):
    runner = _ListRunner(
        [
            {
                "number": 301,
                "title": "fix 49",
                "body": "",
                "headRefName": "ai/fix/49-reddit",
                "headRefOid": "abc",
                "author": {"login": "mikolaj92"},
                "url": "https://example.com/301",
                "isDraft": False,
                "mergeable": "MERGEABLE",
                "labels": [{"name": "ai:generated"}],
            }
        ]
    )
    cfg, repo = _cfg(tmp_path)
    prs = list_open_ai_prs(runner, cfg, repo, live=True)
    assert [pr.number for pr in prs] == [301]
    assert runner.calls[0][runner.calls[0].index("--limit") + 1] == str(SURVEY_LIST_CAP)
