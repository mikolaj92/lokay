
import pytest
import json

from lokay.passkit import io as pass_io
from lokay.proc import dispatch_implement as dispatch


@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_product_repo_is_skipped_before_intake_or_detach(monkeypatch, tmp_path):
    begin = {
        "live": True,
        "issue_budget": 1,
        "stuck_path": str(tmp_path / "stuck.json"),
    }
    working = {
        "actions": [],
        "progress": 0,
        "stuck": {},
        "remaining_ready": 1,
        "ready_by_repo": {
            "mikolaj92/Temida": [
                {"repo": "mikolaj92/Temida", "number": 540, "title": "product"}
            ]
        },
    }
    (tmp_path / "begin.json").write_text(json.dumps(begin), encoding="utf-8")
    (tmp_path / "working.json").write_text(json.dumps(working), encoding="utf-8")
    (tmp_path / "implement.json").write_text(
        json.dumps({"clean_repos": ["mikolaj92/Temida"], "issue_budget": 1}),
        encoding="utf-8",
    )
    monkeypatch.setattr(pass_io, "begin_path", lambda _p: tmp_path / "begin.json")
    monkeypatch.setattr(pass_io, "working_path", lambda _p: tmp_path / "working.json")
    monkeypatch.setattr(pass_io, "implement_path", lambda _p: tmp_path / "implement.json")
    monkeypatch.setattr(dispatch, "_live_ps_text", lambda: "")
    monkeypatch.setattr(
        dispatch,
        "run_proc",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not run intake/label/close")),
    )
    monkeypatch.setattr(
        dispatch,
        "detach_issue_to_pr",
        lambda **_k: (_ for _ in ()).throw(AssertionError("must not detach")),
    )
    monkeypatch.setattr(dispatch, "save_stuck", lambda *_a, **_k: None)
    monkeypatch.setattr(dispatch, "write_pass_receipt", lambda *_a, **_k: None)
    monkeypatch.setattr(dispatch, "build_pass_receipt", lambda **_k: {})

    result = dispatch.run_dispatch_implement(
        pass_dir=str(tmp_path), config_path=None, live=True
    )

    assert result == {
        "ok": True,
        "pass_dir": str(tmp_path),
        "started": 0,
        "detached": False,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "skipped_repos": ["mikolaj92/Temida"],
    }
    saved = json.loads((tmp_path / "working.json").read_text(encoding="utf-8"))
    assert saved["ready_by_repo"] == working["ready_by_repo"]
    assert saved["actions"] == [
        {
            "step": "skip_repo_outside_mini_mill",
            "repo": "mikolaj92/Temida",
            "skipped": True,
            "reason": "repo_not_delivered_by_mini_mill",
        }
    ]
