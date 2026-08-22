
import pytest
from pathlib import Path

from lokay.passkit import io as pass_io
from lokay.proc import survey_prs


@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_mini_mill_lists_only_lokay_prs(tmp_path: Path, monkeypatch) -> None:
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "live": True,
            "repos": ["mikolaj92/Temida", "mikolaj92/lokay"],
        },
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {"actions": [], "survey_errors": 0},
    )
    called: list[str] = []

    def fake_run_proc(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        called.append(repo)
        return {"ok": True, "prs": [{"number": 416}]}

    monkeypatch.setattr(survey_prs, "run_proc", fake_run_proc)

    result = survey_prs.run_survey_prs(
        pass_dir=str(pass_dir), config_path=None, live=True
    )

    assert result["ok"] is True
    assert called == ["mikolaj92/lokay"]
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["prs_by_repo"] == {
        "mikolaj92/Temida": [],
        "mikolaj92/lokay": [{"number": 416}],
    }
    assert any(
        action.get("step") == "skip_pr_survey_outside_mini_scope"
        and action.get("repo") == "mikolaj92/Temida"
        for action in working["actions"]
    )
