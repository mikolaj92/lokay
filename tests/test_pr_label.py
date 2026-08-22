"""Atomic pr_label repository boundary."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from lokay.proc import pr_label




def test_lokay_repo_still_adds_labels(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = SimpleNamespace(pr_labels=("ai:generated",))
    sentinel_runner = object()
    calls: list[tuple[object, str, int, list[str], bool]] = []

    monkeypatch.setattr(pr_label, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(
        pr_label,
        "mutations_allowed",
        lambda *, live_flag, cfg: live_flag,
    )
    monkeypatch.setattr(pr_label, "runner", lambda: sentinel_runner)
    monkeypatch.setattr(
        pr_label,
        "add_pr_labels",
        lambda label_runner, repo, pr, labels, *, live: calls.append(
            (label_runner, repo, pr, labels, live)
        ),
    )

    assert (
        pr_label.main(
            ["--repo", "mikolaj92/lokay", "--pr", "480", "--live"]
        )
        == 0
    )
    assert calls == [
        (sentinel_runner, "mikolaj92/lokay", 480, ["ai:generated"], True)
    ]
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "planned": False,
        "applied": True,
        "repo": "mikolaj92/lokay",
        "pr": 480,
        "labels": ["ai:generated"],
    }


def test_add_pr_labels_propagates_mutation_failure() -> None:
    from lokay.gh_prs import add_pr_labels
    from lokay.runner import CommandResult

    class FailingRunner:
        def run(self, spec, *, live):
            # ensure_labels create succeeds; PR edit fails.
            code = 1 if "pr" in spec.argv and "edit" in spec.argv else 0
            return CommandResult(spec=spec, executed=live, returncode=code, stderr="denied")

        def run_checked(self, spec, *, live):
            result = self.run(spec, live=live)
            if live and result.returncode != 0:
                raise RuntimeError("denied")
            return result

    with pytest.raises(RuntimeError, match="denied"):
        add_pr_labels(
            FailingRunner(), "mikolaj92/lokay", 480, ["ai:generated"], live=True
        )
