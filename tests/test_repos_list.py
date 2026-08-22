from __future__ import annotations

import pytest

import json
from pathlib import Path
from types import SimpleNamespace

from lokay.proc import repos_list


def _repo(name: str, *, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        clone_path=Path("/tmp") / name.split("/")[-1],
        priority=0,
        enabled=enabled,
        note="",
    )


@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_repos_list_only_returns_lokay(monkeypatch, capsys) -> None:
    lokay = _repo("mikolaj92/lokay")
    temida = _repo("mikolaj92/Temida")
    takt = _repo("mikolaj92/takt")
    cfg = SimpleNamespace(
        repos=[lokay, temida, takt],
        active_repos=lambda: [lokay, temida, takt],
    )
    monkeypatch.setattr(repos_list, "load_cfg", lambda _args: cfg)

    assert repos_list.main([]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["enabled"] == 1
    assert payload["disabled"] == 0
    assert [repo["name"] for repo in payload["repos"]] == ["mikolaj92/lokay"]
