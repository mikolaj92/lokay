from pathlib import Path
from types import SimpleNamespace

from lokay.compose import human_mailbox


def test_human_mailbox_lists_only_lokay(tmp_path: Path, monkeypatch) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: live
repos:
  - name: mikolaj92/Temida
    clone_path: {tmp_path / "temida"}
  - name: mikolaj92/lokay
    clone_path: {tmp_path / "lokay"}
""",
        encoding="utf-8",
    )
    issue_calls: list[str] = []
    pr_calls: list[str] = []

    def fake_issues(runner, cfg, repo, *, label, live):
        issue_calls.append(repo.name)
        return [
            SimpleNamespace(
                number=434, title="feedback", url="https://example.test/434"
            )
        ]

    def fake_prs(runner, cfg, repo, *, live):
        pr_calls.append(repo.name)
        return [
            SimpleNamespace(
                number=435,
                title="review",
                url="https://example.test/435",
                labels=["ai:needs-review"],
            )
        ]

    monkeypatch.setattr(human_mailbox, "list_issues_with_label", fake_issues)
    monkeypatch.setattr(human_mailbox, "list_open_ai_prs", fake_prs)

    result = human_mailbox.compose_human_mailbox(
        config_path=str(cfg_path), live=True
    )

    assert issue_calls == ["mikolaj92/lokay"]
    assert pr_calls == ["mikolaj92/lokay"]
    assert result["repos"] == ["mikolaj92/lokay"]
    assert [item["repo"] for item in result["items"]] == [
        "mikolaj92/lokay",
        "mikolaj92/lokay",
    ]
