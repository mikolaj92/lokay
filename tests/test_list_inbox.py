from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lokay.models import Issue
from lokay.proc import list_inbox


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
def test_list_inbox_skips_non_lokay_without_gh(
    repo: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(list_inbox, "load_cfg", lambda _args: _cfg(tmp_path))
    monkeypatch.setattr(list_inbox, "read_live", lambda _args: True)

    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("non-lokay repositories must not call GitHub")

    monkeypatch.setattr(list_inbox, "runner", fail_if_called)
    monkeypatch.setattr(list_inbox, "list_inbox_issues", fail_if_called)

    assert list_inbox.main(["--repo", repo, "--live"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "ok": True,
        "offline": False,
        "repo": repo,
        "issues": [],
        "count": 0,
        "actions": [],
    }


def test_list_inbox_still_lists_lokay_and_skips_stuck_blocked_issue(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    state_path = tmp_path / "state.jsonl"
    stuck_path = state_path.with_name("stuck.json")
    stuck_path.write_text(
        '{"issues": {"mikolaj92/lokay#1": {"blocked": true}}}\n',
        encoding="utf-8",
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "mode: dry-run\n"
        f"state:\n  path: {state_path}\n"
        "repos:\n"
        f"  - name: mikolaj92/lokay\n    clone_path: {tmp_path}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        list_inbox,
        "list_inbox_issues",
        lambda *args, **kwargs: [
            Issue(
                repo="mikolaj92/lokay",
                number=1,
                title="blocked",
                body="",
                labels=[],
                assignees=[],
                url="",
            ),
            Issue(
                repo="mikolaj92/lokay",
                number=2,
                title="inbox",
                body="",
                labels=[],
                assignees=[],
                url="",
            ),
        ],
    )

    result = list_inbox.main(
        ["--config", str(config_path), "--repo", "mikolaj92/lokay"]
    )

    assert result == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert [issue["number"] for issue in payload["issues"]] == [2]
    assert payload["count"] == 1
    assert payload["actions"] == [
        {
            "step": "skip_inbox_stuck_blocked",
            "repo": "mikolaj92/lokay",
            "issues": [1],
        }
    ]
