"""Scope tests for the PR-finalization organ."""

from __future__ import annotations

from typing import Any

import pytest

from lokay.organ import pr_finalize


def _ctx(repo: str) -> dict[str, Any]:
    return {"cfg": ["--config", "config.yaml"], "live": ["--live"], "repo": repo}


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
@pytest.mark.parametrize("atom", ["list_prs", "pr_label"])
@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_product_repo_skips_before_running_finalize_atoms(
    repo: str, atom: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("product repo reached a PR-finalization process")

    monkeypatch.setattr(pr_finalize, "_run_atom_main", fail)

    out = pr_finalize.handle_pr_finalize(
        atom,
        {},
        {
            "make_branch": {"branch": "ai/fix/534-scope"},
            "list_prs": {"prs": [{"number": 12, "head_ref": "ai/fix/534-scope"}]},
        },
        _ctx(repo),
    )

    assert out == {
        "ok": True,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
    }


@pytest.mark.parametrize("atom", ["list_prs", "pr_label"])
def test_lokay_repo_runs_finalize_atoms(
    atom: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def record(_main: object, argv: list[str]) -> dict[str, object]:
        calls.append(argv)
        return {"ok": True}

    monkeypatch.setattr(pr_finalize, "_run_atom_main", record)

    out = pr_finalize.handle_pr_finalize(
        atom,
        {},
        {
            "make_branch": {"branch": "ai/fix/534-scope"},
            "list_prs": {"prs": [{"number": 12, "head_ref": "ai/fix/534-scope"}]},
        },
        _ctx("mikolaj92/lokay"),
    )

    assert out == {"ok": True}
    assert calls == [
        [
            "--config",
            "config.yaml",
            *(["--live"] if atom == "pr_label" else []),
            "--repo",
            "mikolaj92/lokay",
            *(["--pr", "12"] if atom == "pr_label" else []),
        ]
    ]
