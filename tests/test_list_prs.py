from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lokay.code import github as github_code
from lokay.proc import list_prs


def _cfg(tmp_path: Path) -> SimpleNamespace:
    repos = [
        SimpleNamespace(name="mikolaj92/lokay", clone_path=tmp_path / "lokay"),
        SimpleNamespace(name="mikolaj92/Temida", clone_path=tmp_path / "Temida"),
        SimpleNamespace(name="mikolaj92/takt", clone_path=tmp_path / "takt"),
    ]
    return SimpleNamespace(repos=repos, worktrees_root=tmp_path, mode="live")


def test_list_prs_still_lists_lokay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = _cfg(tmp_path)
    sentinel_runner = object()
    seen: list[tuple[object, object, object, bool]] = []
    pr = SimpleNamespace(number=453, title="", body="", head_ref="ai/fix/453", to_dict=lambda: {"number": 453})

    monkeypatch.setattr(list_prs, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(list_prs, "read_live", lambda _args: True)
    monkeypatch.setattr(list_prs, "runner", lambda loaded_cfg: sentinel_runner)

    def fake_list(runner: object, loaded_cfg: object, repo: object, *, live: bool) -> list[object]:
        seen.append((runner, loaded_cfg, repo, live))
        return [pr]

    monkeypatch.setattr(github_code, "list_open_ai_prs", fake_list)

    assert list_prs.main(["--repo", "mikolaj92/lokay", "--live"]) == 0

    assert len(seen) == 1
    assert seen[0][0] is sentinel_runner
    assert seen[0][1] is cfg
    assert seen[0][2].name == "mikolaj92/lokay"
    assert seen[0][3] is True
    payload = json.loads(capsys.readouterr().out)
    assert payload["repo"] == "mikolaj92/lokay"
    assert payload["prs"] == [{"number": 453}]
    assert payload["count"] == 1
