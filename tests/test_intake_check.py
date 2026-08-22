"""CLI boundary tests for the atomic intake check."""

from __future__ import annotations

import json


from lokay.proc import intake_check




def test_lokay_repo_still_fetches_issue(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(intake_check, "load_cfg", lambda args: object())
    monkeypatch.setattr(intake_check, "read_live", lambda args: False)
    monkeypatch.setattr(intake_check, "runner", lambda: object())

    def get_issue(*args, **kwargs):
        calls.append((args, kwargs))
        return None

    monkeypatch.setattr(intake_check, "get_issue", get_issue)

    code = intake_check.main(
        ["--repo", "mikolaj92/lokay", "--issue", "516", "--check", "open"]
    )

    output = json.loads(capsys.readouterr().out)
    assert code != 0
    assert output["ok"] is False
    assert calls
