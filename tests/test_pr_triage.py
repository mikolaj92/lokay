"""Repository boundary for PR triage composition."""

from __future__ import annotations

import pytest

from lokay.compose import pr_triage




def test_factory_repo_still_runs_pr_triage_path(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def run(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(pr_triage, "run_path", run)
    monkeypatch.setattr(pr_triage, "load_config", lambda _path: (_ for _ in ()).throw(RuntimeError))

    result = pr_triage.compose_pr_triage(
        config_path=None,
        repo="mikolaj92/lokay",
        pr_number=526,
        branch="ai/fix/526-pr-triage",
        live=False,
    )

    assert calls == [{
        "path_id": "pr_triage",
        "repo": "mikolaj92/lokay",
        "pr": 526,
        "branch": "ai/fix/526-pr-triage",
        "config_path": None,
        "live": False,
        "package_path": None,
        "extra_inputs": {"keep_issue_open": False},
    }]
    assert result == {
        "ok": True,
        "kind": "pr_triage",
        "engine": "fala",
        "planned": True,
    }
