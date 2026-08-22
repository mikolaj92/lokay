from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lokay.proc import list_issues


def _cfg(tmp_path: Path) -> SimpleNamespace:
    repos = [
        SimpleNamespace(name="mikolaj92/lokay", clone_path=tmp_path / "lokay"),
        SimpleNamespace(name="mikolaj92/Temida", clone_path=tmp_path / "Temida"),
        SimpleNamespace(name="mikolaj92/takt", clone_path=tmp_path / "takt"),
    ]
    return SimpleNamespace(repos=repos, worktrees_root=tmp_path, mode="live")




@pytest.mark.parametrize("label", [None, "work:ready"])
def test_list_issues_still_lists_lokay(
    label: str | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = _cfg(tmp_path)
    sentinel_runner = object()
    seen: list[tuple[str, object, object, object, object]] = []
    issue = SimpleNamespace(to_dict=lambda: {"number": 455})

    monkeypatch.setattr(list_issues, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(list_issues, "read_live", lambda _args: True)
    monkeypatch.setattr(list_issues, "runner", lambda loaded_cfg: sentinel_runner)

    def fake_ready(
        issue_runner: object, loaded_cfg: object, repo: object, *, live: bool
    ) -> list[object]:
        seen.append(("ready", issue_runner, loaded_cfg, repo, live))
        return [issue]

    def fake_label(
        issue_runner: object,
        loaded_cfg: object,
        repo: object,
        *,
        label: str,
        live: bool,
    ) -> list[object]:
        seen.append((label, issue_runner, loaded_cfg, repo, live))
        return [issue]

    monkeypatch.setattr(list_issues, "list_ready_issues", fake_ready)
    monkeypatch.setattr(list_issues, "list_issues_with_label", fake_label)
    argv = ["--repo", "mikolaj92/lokay", "--live"]
    if label:
        argv += ["--label", label]

    assert list_issues.main(argv) == 0

    assert seen == [(label or "ready", sentinel_runner, cfg, cfg.repos[0], True)]
    payload = json.loads(capsys.readouterr().out)
    assert payload["repo"] == "mikolaj92/lokay"
    assert payload["issues"] == [{"number": 455}]
    assert payload["count"] == 1
