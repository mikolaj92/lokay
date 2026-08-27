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

def test_slice_package_keeps_one_path():
    from lokay.graph_run import _slice_package_to_path, find_default_package

    text = find_default_package().read_text(encoding="utf-8")
    sliced = _slice_package_to_path(text, "factory_pass")
    assert 'id = "factory_pass"' in sliced
    assert sliced.count("[[correlation_paths]]") == 1
    assert "[[capabilities]]" in sliced
    # factory_pass has a thin reap_over_budget atom; the catalog path stays out
    assert "select_budget_receipt_1" not in sliced
    assert "prepare_over_budget_reap" not in sliced
    assert 'id = "issue_to_pr"' not in sliced


def test_overlapping_coding_execution_uses_isolated_journals(tmp_path, monkeypatch):
    from lokay import graph_run

    home = tmp_path / "home"
    captured: list = []

    def fake_host(**kwargs):
        captured.append(kwargs["db_path"])
        return {"ok": True, "run_status": "completed", "effector_results": {}}

    monkeypatch.setattr(
        "lokay.proc.child_fala_journal.Path.home",
        lambda *_args, **_kwargs: home,
    )
    monkeypatch.setattr("fala.host_run_package", fake_host)
    package = graph_run.find_default_package()
    for issue in (4999, 4996):
        graph_run.run_path(
            path_id="coding_execution",
            repo="mikolaj92/Temida",
            issue=issue,
            live=False,
            package_path=package,
        )
    assert len(captured) == 2
    assert captured[0] != captured[1]
    shared = home / ".lokay" / "fala" / "state.sqlite"
    assert captured[0] != shared and captured[1] != shared
    assert "coding" in str(captured[0]) and "4999" in str(captured[0])
    assert "coding" in str(captured[1]) and "4996" in str(captured[1])


def test_slice_package_unknown_path():
    from lokay.graph_run import _slice_package_to_path

    try:
        _slice_package_to_path('version = "2"\n[[correlation_paths]]\nid = "x"\n', "nope")
    except ValueError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("expected ValueError")

