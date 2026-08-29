"""LEAF list_open_prs: live GitHub mill PRs. No 30-slot catalog fail."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from lokay.proc.list_open_prs import _keep_mill, run


def _cfg(names: list[str], *, prefix: str = "ai/fix") -> SimpleNamespace:
    return SimpleNamespace(
        branch_prefix=prefix,
        active_repos=lambda: [
            SimpleNamespace(name=name, clone_path=Path("/tmp") / name.replace("/", "__"))
            for name in names
        ],
    )


def _result(*, returncode: int = 0, stdout: str = "[]", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr, timed_out=False)


class Git:
    def run(self, spec, *, live):
        return _result()

    def run_checked(self, spec, *, live):
        result = self.run(spec, live=live)
        if live and result.returncode != 0:
            raise RuntimeError(result.stderr or "command failed")
        return result


def test_keep_mill_is_a_small_function() -> None:
    kept = _keep_mill(
        [
            {"pr": 9, "branch": "ai/fix/9-x"},
            {"pr": 10, "branch": "feat/human"},
        ],
        "ai/fix",
    )
    assert [row["pr"] for row in kept] == [9]


def test_empty_list_is_ok(monkeypatch) -> None:
    monkeypatch.setattr("lokay.proc.list_open_prs.load_cfg", lambda _args: _cfg(["o/r"]))

    monkeypatch.setattr("lokay.proc.list_open_prs.runner", lambda: Git())
    assert run(config_path=None, live=True) == {"ok": True, "prs": [], "count": 0}


def test_lists_live_mill_prs(monkeypatch) -> None:
    monkeypatch.setattr(
        "lokay.proc.list_open_prs.load_cfg",
        lambda _args: _cfg(["mikolaj92/lokay"]),
    )

    class Listing(Git):
        def run(self, spec, *, live):
            assert spec.argv[:3] == ("gh", "pr", "list")
            return _result(
                stdout=json.dumps(
                    [
                        {
                            "number": 9,
                            "title": "mill",
                            "headRefName": "ai/fix/9-x",
                            "headRefOid": "abc",
                            "author": {"login": "mikolaj92"},
                            "url": "https://github.com/mikolaj92/lokay/pull/9",
                            "isDraft": False,
                            "mergeable": "MERGEABLE",
                            "labels": [],
                        },
                        {
                            "number": 10,
                            "title": "human",
                            "headRefName": "feat/human",
                            "headRefOid": "def",
                            "author": {"login": "human"},
                            "url": "https://github.com/mikolaj92/lokay/pull/10",
                            "isDraft": False,
                            "mergeable": "MERGEABLE",
                            "labels": [],
                        },
                    ]
                )
            )

    monkeypatch.setattr("lokay.proc.list_open_prs.runner", lambda: Listing())
    out = run(config_path=None, live=True)
    assert out["ok"] is True
    assert out["count"] == 1
    assert out["prs"][0]["pr"] == 9


def test_forty_repos_do_not_catalog_fail(monkeypatch) -> None:
    names = [f"o/r{i}" for i in range(40)]
    monkeypatch.setattr("lokay.proc.list_open_prs.load_cfg", lambda _args: _cfg(names))

    class Listing(Git):
        def run(self, spec, *, live):
            repo = spec.argv[spec.argv.index("--repo") + 1]
            return _result(
                stdout=json.dumps(
                    [
                        {
                            "number": 1,
                            "title": repo,
                            "headRefName": "ai/fix/1-x",
                            "headRefOid": "abc",
                            "author": {"login": "x"},
                            "url": f"https://github.com/{repo}/pull/1",
                            "isDraft": False,
                            "mergeable": "MERGEABLE",
                            "labels": [],
                        }
                    ]
                )
            )

    monkeypatch.setattr("lokay.proc.list_open_prs.runner", lambda: Listing())
    out = run(config_path=None, live=True)
    assert out["ok"] is True
    assert out["count"] == 40
    assert out.get("reason") != "leftover_overflow"


def test_dry_run_is_empty(monkeypatch) -> None:
    monkeypatch.setattr("lokay.proc.list_open_prs.load_cfg", lambda _args: _cfg(["o/r"]))

    class GitBad(Git):
        def run(self, spec, *, live):
            return _result(stdout="not-json")

    monkeypatch.setattr("lokay.proc.list_open_prs.runner", lambda: GitBad())
    assert run(config_path=None, live=False) == {"ok": True, "prs": [], "count": 0}
