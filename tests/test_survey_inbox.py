from pathlib import Path

from lokay.envelope import emit_exit, ok
from lokay.passkit import io as pass_io
from lokay.proc import survey_inbox


def test_mini_mill_lists_only_lokay_inbox(tmp_path: Path, monkeypatch) -> None:
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {"repos": ["mikolaj92/Temida", "mikolaj92/lokay"]},
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {"actions": [], "survey_errors": 0},
    )
    called: list[str] = []

    def fake_run_proc(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        called.append(repo)
        return {"ok": True, "issues": [{"number": 421}]}

    monkeypatch.setattr(survey_inbox, "run_proc", fake_run_proc)

    result = survey_inbox.run_survey_inbox(
        pass_dir=str(pass_dir), config_path=None, live=True
    )

    assert result["ok"] is True
    assert called == ["mikolaj92/lokay"]
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["inbox_by_repo"] == {
        "mikolaj92/Temida": 0,
        "mikolaj92/lokay": 1,
    }
    assert working["inbox_issues_by_repo"] == {
        "mikolaj92/Temida": [],
        "mikolaj92/lokay": [{"number": 421}],
    }
    assert working["remaining_inbox"] == 1
    assert any(
        action.get("step") == "skip_inbox_survey_outside_mini_scope"
        and action.get("repo") == "mikolaj92/Temida"
        for action in working["actions"]
    )


def test_survey_inbox_skips_blocked_issue(tmp_path: Path, monkeypatch) -> None:
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    stuck_path = tmp_path / "stuck.json"
    stuck_path.write_text(
        '{"issues": {"owner/repo#1": {"blocked": true}}}\n',
        encoding="utf-8",
    )
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "repos": ["owner/repo"],
            "stuck_path": str(stuck_path),
        },
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {"actions": [], "survey_errors": 0},
    )

    def fake_list_inbox(argv=None):
        return emit_exit(
            ok(
                repo="owner/repo",
                issues=[{"number": 1}, {"number": 2}],
                count=2,
            )
        )

    monkeypatch.setattr(survey_inbox.p_list_inbox, "main", fake_list_inbox)

    result = survey_inbox.run_survey_inbox(
        pass_dir=str(pass_dir), config_path=None, live=True
    )

    assert result["ok"] is True
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["inbox_issues_by_repo"]["owner/repo"] == [{"number": 2}]
    assert working["inbox_by_repo"]["owner/repo"] == 1
    assert working["remaining_inbox"] == 1
    assert any(
        action["step"] == "skip_inbox_stuck_blocked"
        and action["repo"] == "owner/repo"
        and action["issues"] == [1]
        for action in working["actions"]
    )
