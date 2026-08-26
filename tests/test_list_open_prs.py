"""Live GitHub list for the prs child. No mill filter. No 30-slot catalog fail."""

from __future__ import annotations

import json
from types import SimpleNamespace

from lokay.proc.list_open_prs import run


def _scope(*names: str) -> dict:
    return {"ok": True, "repos": list(names), "prefix": "ai/fix/"}


def _result(*, returncode: int = 0, stdout: str = "[]", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_empty_list_is_ok(monkeypatch) -> None:
    class Git:
        def run(self, spec, *, live):
            return _result()

    monkeypatch.setattr("lokay.proc.list_open_prs.runner", lambda: Git())
    out = run(_scope("o/r"), live=True)
    assert out == {"ok": True, "prs": [], "count": 0}


def test_lists_live_open_prs_including_human(monkeypatch) -> None:
    class Git:
        def run(self, spec, *, live):
            assert live is True
            assert spec.argv[:3] == ("gh", "pr", "list")
            return _result(
                stdout=json.dumps(
                    [
                        {
                            "number": 9,
                            "title": "mill",
                            "headRefName": "ai/fix/9-x",
                        },
                        {
                            "number": 10,
                            "title": "human",
                            "headRefName": "feat/human",
                        },
                    ]
                )
            )

    monkeypatch.setattr("lokay.proc.list_open_prs.runner", lambda: Git())
    out = run(_scope("mikolaj92/lokay"), live=True)
    assert out["ok"] is True
    assert out["count"] == 2
    assert [row["pr"] for row in out["prs"]] == [9, 10]


def test_forty_repos_do_not_catalog_fail(monkeypatch) -> None:
    names = [f"o/r{i}" for i in range(40)]

    class Git:
        def run(self, spec, *, live):
            repo = spec.argv[spec.argv.index("--repo") + 1]
            return _result(
                stdout=json.dumps(
                    [{"number": 1, "title": repo, "headRefName": "ai/fix/1-x"}]
                )
            )

    monkeypatch.setattr("lokay.proc.list_open_prs.runner", lambda: Git())
    out = run(_scope(*names), live=True)
    assert out["ok"] is True
    assert out["count"] == 40
    assert "catalog" not in str(out).lower()
    assert out.get("reason") != "leftover_overflow"


def test_dry_run_is_empty(monkeypatch) -> None:
    class Git:
        def run(self, spec, *, live):
            assert live is False
            return _result(stdout="not-json")

    monkeypatch.setattr("lokay.proc.list_open_prs.runner", lambda: Git())
    assert run(_scope("o/r"), live=False) == {"ok": True, "prs": [], "count": 0}
