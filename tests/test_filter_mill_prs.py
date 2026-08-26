from lokay.proc.filter_mill_prs import filter_rows
from lokay.proc.read_prs_scope import read


def test_keeps_mill_prefix_only() -> None:
    listed = {
        "ok": True,
        "prs": [
            {"repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"},
            {"repo": "o/r", "pr": 10, "branch": "feat/human"},
        ],
    }
    out = filter_rows(listed, {"prefix": "ai/fix/"})
    assert out["ok"] is True
    assert out["count"] == 1
    assert out["prs"][0]["pr"] == 9


def test_empty_list_stays_ok() -> None:
    assert filter_rows({"ok": True, "prs": []}, {"prefix": "ai/fix/"}) == {
        "ok": True,
        "prs": [],
        "count": 0,
    }


def test_read_prs_scope_is_local(monkeypatch) -> None:
    class Repo:
        def __init__(self, name: str) -> None:
            self.name = name

    class Cfg:
        branch_prefix = "ai/fix"
        def active_repos(self):
            return [Repo("o/a"), Repo("o/b")]

    monkeypatch.setattr("lokay.proc.read_prs_scope.load_cfg", lambda _args: Cfg())
    out = read(config_path=None)
    assert out == {"ok": True, "repos": ["o/a", "o/b"], "prefix": "ai/fix/"}
