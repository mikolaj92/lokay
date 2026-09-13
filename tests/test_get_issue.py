from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from lokay.proc import get_issue


def test_get_issue_still_fetches_lokay(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = object()
    issue = SimpleNamespace(
        repo="mikolaj92/lokay",
        number=459,
        title="",
        body="",
        labels=[],
        assignees=[],
        url="https://github.com/mikolaj92/lokay/issues/459",
        state="OPEN",
        author="",
    )
    sentinel_runner = object()
    seen: list[tuple[object, object, str, int, bool]] = []

    monkeypatch.setattr(get_issue, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(get_issue, "read_live", lambda _args: True)
    monkeypatch.setattr(get_issue, "runner", lambda: sentinel_runner)

    def fake_get_issue(
        issue_runner: object,
        loaded_cfg: object,
        repo: str,
        number: int,
        *,
        live: bool,
    ) -> object:
        seen.append((issue_runner, loaded_cfg, repo, number, live))
        return issue

    monkeypatch.setattr("lokay.github_tasks.view_issue", fake_get_issue)

    assert (
        get_issue.main(
            ["--repo", "mikolaj92/lokay", "--issue", "459", "--live"]
        )
        == 0
    )
    assert seen == [(sentinel_runner, cfg, "mikolaj92/lokay", 459, True)]
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["offline"] is False
    assert payload["issue"]["number"] == 459
    assert payload["issue"]["state"] == "OPEN"


def test_live_task_issue_read_preserves_comment_bodies_for_idempotency():
    from lokay.gh_issues import get_issue as get_task_issue

    class _Runner:
        def __init__(self):
            self.spec = None

        def run(self, spec, *, live):
            assert live is True
            self.spec = spec
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "number": 31,
                        "title": "Identity report",
                        "body": "Details",
                        "labels": [],
                        "assignees": [],
                        "author": {"login": "mikolaj92"},
                        "url": "https://github.com/mikolaj92/dotfiles/issues/31",
                        "state": "OPEN",
                        "comments": [
                            {"body": "Skipped (Lokay intake): obsolete_source_removed."}
                        ],
                    }
                ),
            )

    runner = _Runner()
    issue = get_task_issue(
        runner, SimpleNamespace(), "mikolaj92/dotfiles", 31, live=True
    )

    assert issue.comments == ["Skipped (Lokay intake): obsolete_source_removed."]
    requested_fields = runner.spec.argv[runner.spec.argv.index("--json") + 1].split(",")
    assert "comments" in requested_fields
    assert "comments" not in issue.to_dict()
