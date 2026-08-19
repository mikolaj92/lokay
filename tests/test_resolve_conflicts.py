"""Hermetic scope tests for the resolve-conflicts pass atom."""

from __future__ import annotations

from pathlib import Path

import pytest

from lokay.passkit import io as pass_io
from lokay.proc import pr_close as p_pr_close
from lokay.proc import resolve_conflicts
from lokay.proc import stage_label as p_stage


def _conflicting_pr(number: int) -> dict[str, object]:
    return {
        "number": number,
        "head_ref": f"ai/fix/{number}-conflict",
        "mergeable": "CONFLICTING",
        "title": f"issue {number}",
    }


def _write_pass(tmp_path: Path, repos: list[str]) -> Path:
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "repos": repos,
            "branch_prefix": "ai/fix/",
            "stuck_path": str(tmp_path / "stuck.json"),
        },
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {
            "actions": [],
            "progress": 0,
            "stuck": {"issues": {}},
            "prs_by_repo": {
                repo: [_conflicting_pr(index + 20)]
                for index, repo in enumerate(repos)
            },
            "ready_by_repo": {},
            "remaining_prs": len(repos),
            "remaining_ready": 0,
            "merge_conflicts": 0,
        },
    )
    return pass_dir


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_product_repo_is_skipped_without_mutations(
    repo: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pass_dir = _write_pass(tmp_path, [repo])

    def fail(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("product repo reached a GitHub mutation atom")

    monkeypatch.setattr(resolve_conflicts, "run_proc", fail)

    out = resolve_conflicts.run_resolve_conflicts(
        pass_dir=str(pass_dir), config_path=None, live=True
    )

    assert out["ok"] is True
    assert out["skipped"] is True
    assert out["reason"] == "repo_not_delivered_by_mini_mill"
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["prs_by_repo"][repo] == [_conflicting_pr(20)]
    assert working["remaining_prs"] == 1
    assert working["progress"] == 0
    assert working["actions"] == [
        {
            "step": "skip_resolve_conflicts_outside_mini_scope",
            "repo": repo,
            "reason": "repo_not_delivered_by_mini_mill",
        }
    ]


def test_mixed_catalog_skips_product_and_resolves_lokay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    product = "mikolaj92/Temida"
    lokay = "mikolaj92/lokay"
    pass_dir = _write_pass(tmp_path, [product, lokay])
    calls: list[tuple[object, str]] = []

    def fake_run_proc(fn: object, argv: list[str]) -> dict[str, object]:
        repo = argv[argv.index("--repo") + 1]
        calls.append((fn, repo))
        if fn is p_pr_close.main:
            return {"ok": True, "closed": True}
        if fn is p_stage.main:
            return {"ok": True, "applied": True}
        raise AssertionError(f"unexpected mutation atom: {fn}")

    monkeypatch.setattr(resolve_conflicts, "run_proc", fake_run_proc)

    out = resolve_conflicts.run_resolve_conflicts(
        pass_dir=str(pass_dir), config_path=None, live=True
    )

    assert out["ok"] is True
    assert out["closed"] == 1
    assert out["skipped"] is True
    assert calls == [(p_pr_close.main, lokay), (p_stage.main, lokay)]
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["prs_by_repo"][product] == [_conflicting_pr(20)]
    assert working["prs_by_repo"][lokay] == []
    assert working["remaining_prs"] == 1
    assert working["progress"] == 1
