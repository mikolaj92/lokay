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
                "triage_issue": {
                    "status": "completed",
                    "output": {"values": {"skipped": True}},
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
