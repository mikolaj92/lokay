"""Regression: live factory-pass must not die on list-* --live."""

from __future__ import annotations

from pathlib import Path

from lokay.envelope import emit_exit, ok
from lokay.passkit import io as pass_io
from lokay.passkit.support import run_proc
from lokay.proc import list_inbox, list_issues, list_prs, survey_inbox, survey_prs


def test_list_read_atoms_accept_live_with_offline(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "mode: dry-run\nrepos:\n  - name: mikolaj92/lokay\n    clone_path: /tmp\n",
        encoding="utf-8",
    )
    for main in (list_inbox.main, list_prs.main, list_issues.main):
        code = main(
            ["--config", str(cfg), "--offline", "--live", "--repo", "mikolaj92/lokay"]
        )
        assert code == 0


def test_run_proc_turns_argparse_systemexit_into_envelope() -> None:
    out = run_proc(list_inbox.main, ["--repo", "mikolaj92/lokay", "--not-a-flag"])
    assert out["ok"] is False
    assert out["_exit"] != 0
    assert "unrecognized arguments" in str(out.get("error") or "")


def _pass(tmp_path: Path) -> str:
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {"repos": ["o/r"], "live": True, "branch_prefix": "ai/fix/"},
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir), {"actions": [], "survey_errors": 0}
    )
    return str(pass_dir)


def test_survey_prs_live_forwards_live_without_crash(
    tmp_path: Path, monkeypatch
) -> None:
    seen: list[list[str]] = []

    def fake_main(argv: list[str] | None = None) -> int:
        seen.append(list(argv or []))
        return emit_exit(ok(prs=[], repo="o/r", count=0))

    monkeypatch.setattr(survey_prs.p_list_prs, "main", fake_main)
    out = survey_prs.run_survey_prs(
        pass_dir=_pass(tmp_path), config_path=None, live=True
    )
    assert out["ok"] is True
    assert seen
    assert "--live" in seen[0]


def test_survey_inbox_and_ready_list_forward_live(tmp_path: Path, monkeypatch) -> None:
    from lokay.proc import list_work_ready_issues

    def fake_inbox(argv: list[str] | None = None) -> int:
        assert "--live" in list(argv or [])
        return emit_exit(ok(issues=[], repo="o/r", count=0))

    seen = []

    def fake_issues(argv: list[str] | None = None) -> int:
        seen.append(list(argv or []))
        return emit_exit(ok(issues=[], repo="o/r", count=0))

    monkeypatch.setattr(survey_inbox.p_list_inbox, "main", fake_inbox)
    monkeypatch.setattr(list_work_ready_issues.list_issues, "main", fake_issues)
    inbox = survey_inbox.run_survey_inbox(
        pass_dir=_pass(tmp_path), config_path=None, live=True
    )
    listed = list_work_ready_issues.fetch({"repo": "o/r"}, config_path=None, live=True)
    assert inbox["ok"] is True and listed["route"] == "listed"
    assert "--live" in seen[0]
