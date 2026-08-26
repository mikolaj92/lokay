from lokay.proc.run_pr_triage_subflow import run


def test_skip_when_empty() -> None:
    assert run({"route": "none", "reason": "no_open_pr"}, config_path=None, live=False)[
        "route"
    ] == "skip"


def test_calls_pr_triage(monkeypatch) -> None:
    seen: list[dict] = []

    def fake(**kwargs):
        seen.append(kwargs)
        return {"ok": True, "result": {"merged": True}}

    monkeypatch.setattr(
        "lokay.proc.run_pr_triage_subflow.compose_pr_triage", fake
    )
    out = run(
        {
            "route": "pr",
            "repo": "o/r",
            "pr": 9,
            "branch": "ai/fix/9-x",
        },
        config_path=None,
        live=False,
    )
    assert out["route"] == "completed"
    assert out["ok"] is True
    assert seen == [
        {
            "config_path": None,
            "repo": "o/r",
            "pr_number": 9,
            "branch": "ai/fix/9-x",
            "live": False,
        }
    ]
