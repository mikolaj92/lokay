"""Repository boundary for PR triage composition."""

from __future__ import annotations

import pytest

from lokay.compose import pr_triage


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_product_repo_skips_without_config_fala_or_state(
    repo: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("product repositories must not run config, Fala, or state I/O")

    monkeypatch.setattr(pr_triage, "load_config", fail_if_called)
    monkeypatch.setattr(pr_triage, "run_path", fail_if_called)
    monkeypatch.setattr(pr_triage, "append_event", fail_if_called)

    assert pr_triage.compose_pr_triage(
        config_path=None,
        repo=repo,
        pr_number=526,
        branch="ai/fix/526-product",
        live=True,
    ) == {
        "ok": True,
        "kind": "pr_triage",
        "engine": "fala",
        "planned": False,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
        "pr": 526,
        "branch": "ai/fix/526-product",
    }


def test_lokay_repo_still_runs_pr_triage_path(monkeypatch: pytest.MonkeyPatch) -> None:
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
