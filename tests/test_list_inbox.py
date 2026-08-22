from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace


from lokay.models import Issue
from lokay.proc import list_inbox


def _cfg(tmp_path: Path) -> SimpleNamespace:
    repos = [
        SimpleNamespace(name="mikolaj92/lokay", clone_path=tmp_path / "lokay"),
        SimpleNamespace(name="mikolaj92/Temida", clone_path=tmp_path / "Temida"),
        SimpleNamespace(name="mikolaj92/takt", clone_path=tmp_path / "takt"),
    ]
    return SimpleNamespace(repos=repos, worktrees_root=tmp_path, mode="live")




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


def test_inbox_rate_limit_does_not_stamp_empty(tmp_path, monkeypatch, capsys):
    """Inbox rate limit does not stamp empty."""
    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = 1.0
    os.utime(stamp, (old, old))
    monkeypatch.setattr(list_inbox, "load_cfg", lambda _args: _cfg(tmp_path))
    monkeypatch.setattr(list_inbox, "read_live", lambda _args: True)
    monkeypatch.setattr(list_inbox, "runner", lambda _cfg: object())
    seen: list[bool] = []

    def boom(*_a, **kwargs):
        seen.append("raise_on_rate_limit" in kwargs)
        raise RuntimeError("HTTP 429: API rate limit exceeded")

    monkeypatch.setattr(list_inbox, "list_inbox_issues", boom)

    result = list_inbox.main(["--repo", "mikolaj92/lokay", "--live"])

    assert result == 1
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is False
    assert seen == [False]
    assert stamp.stat().st_mtime == old
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "list_inbox.py"
    assert "Inbox rate limit does not stamp empty." in src.read_text(encoding="utf-8")
