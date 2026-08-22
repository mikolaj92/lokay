from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lokay.proc import list_prs


def _cfg(tmp_path: Path) -> SimpleNamespace:
    repos = [
        SimpleNamespace(name="mikolaj92/lokay", clone_path=tmp_path / "lokay"),
        SimpleNamespace(name="mikolaj92/Temida", clone_path=tmp_path / "Temida"),
        SimpleNamespace(name="mikolaj92/takt", clone_path=tmp_path / "takt"),
    ]
    return SimpleNamespace(repos=repos, worktrees_root=tmp_path, mode="live")


@pytest.mark.parametrize(
    "repo",
    ["mikolaj92/Temida", "mikolaj92/takt", "some-owner/outside-config"],
)
@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_list_prs_skips_non_lokay_without_gh(
    repo: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(list_prs, "load_cfg", lambda _args: _cfg(tmp_path))
    monkeypatch.setattr(list_prs, "read_live", lambda _args: True)

    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("non-lokay repositories must not call GitHub")

    monkeypatch.setattr(list_prs, "runner", fail_if_called)
    monkeypatch.setattr(list_prs, "list_open_ai_prs", fail_if_called)

    assert list_prs.main(["--repo", repo, "--live"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == {"ok": True, "offline": False, "repo": repo, "prs": [], "count": 0}


def test_list_prs_still_lists_lokay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = _cfg(tmp_path)
    sentinel_runner = object()
    seen: list[tuple[object, object, object, bool]] = []
    pr = SimpleNamespace(to_dict=lambda: {"number": 453})

    monkeypatch.setattr(list_prs, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(list_prs, "read_live", lambda _args: True)
    monkeypatch.setattr(list_prs, "runner", lambda loaded_cfg: sentinel_runner)

    def fake_list(runner: object, loaded_cfg: object, repo: object, *, live: bool) -> list[object]:
        seen.append((runner, loaded_cfg, repo, live))
        return [pr]

    monkeypatch.setattr(list_prs, "list_open_ai_prs", fake_list)

    assert list_prs.main(["--repo", "mikolaj92/lokay", "--live"]) == 0

    assert seen == [(sentinel_runner, cfg, cfg.repos[0], True)]
    payload = json.loads(capsys.readouterr().out)
    assert payload["repo"] == "mikolaj92/lokay"
    assert payload["prs"] == [{"number": 453}]
    assert payload["count"] == 1
