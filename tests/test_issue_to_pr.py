"""Repository boundary for issue-to-PR composition."""

from __future__ import annotations

import pytest

from lokay.compose import issue_to_pr




def test_factory_repo_still_runs_issue_to_pr_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def run(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(issue_to_pr, "_await_detach_activation", lambda: True)
    monkeypatch.setattr(issue_to_pr, "run_path", run)
    monkeypatch.setattr(
        issue_to_pr, "load_config", lambda _path: (_ for _ in ()).throw(RuntimeError)
    )

    result = issue_to_pr.compose_issue_to_pr(
        config_path=None,
        repo="mikolaj92/lokay",
        issue_number=530,
        live=False,
    )

    assert calls == [{
        "path_id": "issue_to_pr",
        "repo": "mikolaj92/lokay",
        "issue": 530,
        "config_path": None,
        "live": False,
        "package_path": None,
        "extra_inputs": {
            "incident_fingerprint": "",
            "keep_issue_open": False,
            "work_id": "mikolaj92/lokay#530",
        },
    }]
    assert result == {
        "ok": True,
        "kind": "issue_to_pr",
        "engine": "fala",
        "planned": True,
        "work_id": "mikolaj92/lokay#530",
        "work_state": "planned",
    }
