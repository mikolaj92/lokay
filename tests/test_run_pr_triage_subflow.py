from lokay.proc.run_pr_triage_subflow import CHILD_PATH, run


def test_named_slot_is_pr_triage() -> None:
    assert CHILD_PATH == "pr_triage"


def test_launches_child_path_only(monkeypatch) -> None:
    seen: list[dict] = []

    def fake(**kwargs):
        seen.append(kwargs)
        return {"ok": True, "result": {"merged": True}}

    monkeypatch.setattr("lokay.proc.run_pr_triage_subflow.run_path", fake)
    out = run(
        {"route": "pr", "repo": "o/r", "pr": 9, "branch": "ai/fix/9-x"},
        config_path=None,
        live=False,
    )
    assert out["route"] == "completed"
    assert seen == [
        {
            "path_id": "pr_triage",
            "repo": "o/r",
            "pr": 9,
            "branch": "ai/fix/9-x",
            "config_path": None,
            "live": False,
        }
    ]
