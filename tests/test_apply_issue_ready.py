from types import SimpleNamespace

from lokay.proc.apply_issue_ready import apply


class _Runner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run_checked(self, spec, *, live: bool):
        self.calls.append(" ".join(spec.argv))
        return SimpleNamespace(returncode=0, stdout="", stderr="")


def test_ready_does_not_add_lokaj_beside_pawel():
    runner = _Runner()
    cfg = SimpleNamespace(assignee="mikolaj92", ready_label="ai:ready")
    out = apply(
        runner=runner,
        cfg=cfg,
        repo="Temida/Temida",
        issue=5072,
        issue_data={"labels": ["ai:ready", "work:ready"], "assignees": ["PSyron"]},
        live=True,
    )
    assert out["ok"] is True
    assert runner.calls == []


def test_ready_assigns_lokaj_when_empty():
    runner = _Runner()
    cfg = SimpleNamespace(assignee="mikolaj92", ready_label="ai:ready")
    out = apply(
        runner=runner,
        cfg=cfg,
        repo="o/r",
        issue=1,
        issue_data={"labels": ["ai:ready", "work:ready"], "assignees": []},
        live=True,
    )
    assert out["ok"] is True
    assert any("--add-assignee mikolaj92" in c for c in runner.calls)
