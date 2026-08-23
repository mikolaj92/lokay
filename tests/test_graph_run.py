import json


def test_run_path_suppresses_host_envelope_stdout(monkeypatch, tmp_path, capsys):
    from lokay import graph_run

    dumped = {
        "terminal": {"large": "x" * 10_000},
        "steps": [{"large": "x" * 10_000}],
        "last": {"large": "x" * 10_000},
    }

    def noisy_host(**_kwargs):
        print(json.dumps(dumped))
        return {
            "ok": True,
            "run_status": "completed",
            "effector_results": {
                "finalize_issue_triage": {
                    "status": "completed",
                    "output": {"values": {"decision": {"verdict": "skip"}}},
                }
            },
            **dumped,
        }

    monkeypatch.setattr("fala.host_run_package", noisy_host)

    result = graph_run.run_path(
        path_id="issue_triage",
        repo="owner/repo",
        issue=343,
        package_path=graph_run.find_default_package(),
        db_path=tmp_path,
    )

    assert capsys.readouterr().out == ""
    assert result["fala"]["terminal"] == dumped["terminal"]
    assert result["fala"]["steps"] == dumped["steps"]
    assert result["fala"]["last"] == dumped["last"]


def test_normalize_prefers_authored_terminal_result():
    result = {
        "ok": True,
        "path_id": "issue_to_pr_delivery",
        "live": True,
        "fala": {
            "effector_results": {
                "summarize_issue_delivery": {
                    "id": "x:summarize_issue_delivery",
                    "status": "succeeded",
                    "output": {
                        "values": {
                            "ok": True,
                            "result": {
                                "pr": 77,
                                "branch": "ai/fix/7",
                                "delivered": True,
                            },
                        }
                    },
                }
            }
        },
    }
    from lokay.graph_run import normalize_path_result

    out = normalize_path_result(result)
    assert out["ok"] is True and out["pr"] == 77 and out["branch"] == "ai/fix/7"
