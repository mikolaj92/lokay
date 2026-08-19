from __future__ import annotations

import json
from pathlib import Path

from lokay.models import Issue
from lokay.proc import list_inbox


def test_list_inbox_skips_stuck_blocked_issue(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    state_path = tmp_path / "state.jsonl"
    stuck_path = state_path.with_name("stuck.json")
    stuck_path.write_text(
        '{"issues": {"owner/repo#1": {"blocked": true}}}\n',
        encoding="utf-8",
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "mode: dry-run\n"
        f"state:\n  path: {state_path}\n"
        "repos:\n"
        f"  - name: owner/repo\n    clone_path: {tmp_path}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        list_inbox,
        "list_inbox_issues",
        lambda *args, **kwargs: [
            Issue(
                repo="owner/repo",
                number=1,
                title="blocked",
                body="",
                labels=[],
                assignees=[],
                url="",
            ),
            Issue(
                repo="owner/repo",
                number=2,
                title="inbox",
                body="",
                labels=[],
                assignees=[],
                url="",
            ),
        ],
    )

    result = list_inbox.main(["--config", str(config_path), "--repo", "owner/repo"])

    assert result == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert [issue["number"] for issue in payload["issues"]] == [2]
    assert payload["count"] == 1
    assert payload["actions"] == [
        {
            "step": "skip_inbox_stuck_blocked",
            "repo": "owner/repo",
            "issues": [1],
        }
    ]
