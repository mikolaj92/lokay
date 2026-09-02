import json
from pathlib import Path


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
    monkeypatch.delenv("LOKAY_ROOT", raising=False)

    result = graph_run.run_path(
        path_id="issue_triage",
        repo="owner/repo",
        issue=343,
        package_path=graph_run.find_default_package(),
        db_path=tmp_path,
    )

    assert capsys.readouterr().out == ""
    assert graph_run.os.environ["LOKAY_ROOT"] == str(graph_run._project_root())
    assert result["fala"]["terminal"] == dumped["terminal"]
    assert result["fala"]["steps"] == dumped["steps"]
    assert result["fala"]["last"] == dumped["last"]


def test_factory_pass_cleanup_process_failed_still_opens_a_pr():
    """Leftover work-copy process.failed is a classified route. Issues can PR."""
    from lokay.graph_run import normalize_path_result

    out = normalize_path_result(
        {
            "ok": False,
            "path_id": "factory_pass",
            "fala": {
                "run_status": "failed",
                "effector_results": {
                    "factory_begin": {
                        "status": "succeeded",
                        "output": {"values": {"ok": True, "pass_dir": "/pass"}},
                    },
                    "prs": {
                        "status": "succeeded",
                        "output": {"values": {"ok": True}},
                    },
                    "reap_stale_worktrees": {
                        "status": "failed",
                        "error": "cleanup process.failed",
                        "output": {"values": {}},
                    },
                    "issues": {
                        "status": "succeeded",
                        "output": {
                            "values": {
                                "ok": True,
                                "route": "do",
                                "launched": "pr",
                                "result": {"launched": "pr", "leftover": 1},
                            }
                        },
                    },
                    "record_pass": {
                        "status": "succeeded",
                        "output": {
                            "values": {
                                "ok": True,
                                "result": {"outcome": "new_pr", "ok": True},
                            }
                        },
                    },
                    "factory_pass_terminal": {
                        "status": "succeeded",
                        "output": {
                            "values": {
                                "ok": True,
                                "result": {"outcome": "new_pr", "ok": True},
                            }
                        },
                    },
                },
            },
        }
    )
    assert out["ok"] is True
    assert out["outcome"] == "new_pr"
    assert out["terminal"]["reap_stale_worktrees"]["route"] == "failed"
    assert out["terminal"]["issues"]["launched"] == "pr"


def test_factory_pass_prefixed_reap_adapter_failed_still_opens_a_pr():
    """Sibling reap adapter_failed must not fail the factory_pass parent."""
    from lokay.graph_run import normalize_path_result

    out = normalize_path_result(
        {
            "ok": False,
            "error": "adapter_failed",
            "path_id": "factory_pass",
            "fala": {
                "run_status": "failed",
                "error": "adapter_failed",
                "effector_results": {
                    "factory_begin": {
                        "status": "succeeded",
                        "output": {"values": {"ok": True, "pass_dir": "/pass"}},
                    },
                    "prs": {
                        "status": "succeeded",
                        "output": {"values": {"ok": True}},
                    },
                    "run-abc:reap_stale_worktrees": {
                        "id": "run-abc:reap_stale_worktrees",
                        "status": "failed",
                        "error": "adapter_failed",
                        "output": {"values": {}},
                    },
                    "issues": {
                        "status": "succeeded",
                        "output": {
                            "values": {
                                "ok": True,
                                "route": "do",
                                "launched": "pr",
                                "result": {"launched": "pr", "leftover": 3},
                            }
                        },
                    },
                    "record_pass": {
                        "status": "succeeded",
                        "output": {
                            "values": {
                                "ok": True,
                                "result": {"outcome": "new_pr", "ok": True},
                            }
                        },
                    },
                    "factory_pass_terminal": {
                        "status": "succeeded",
                        "output": {
                            "values": {
                                "ok": True,
                                "result": {"outcome": "new_pr", "ok": True},
                            }
                        },
                    },
                },
            },
        }
    )
    assert out["ok"] is True
    assert out["outcome"] == "new_pr"
    assert "adapter_failed" not in str(out.get("error") or "")
    assert out["terminal"]["reap_stale_worktrees"]["route"] == "failed"
    assert out["terminal"]["issues"]["launched"] == "pr"


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

def test_run_path_uses_global_inputs_not_per_effector(monkeypatch, tmp_path):
    from lokay import graph_run

    captured = {}

    def host(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "run_status": "completed", "effector_results": {}}

    monkeypatch.setattr("fala.host_run_package", host)
    graph_run.run_path(
        path_id="status_snapshot",
        repo="owner/repo",
        issue=7,
        pr=9,
        branch="ai/fix/7",
        live=False,
        package_path=graph_run.find_default_package(),
        db_path=tmp_path,
        require_healthy=False,
        extra_inputs={"foo": "bar"},
    )
    assert captured.get("effector_inputs") in (None, {})
    assert captured["path_id"] == "status_snapshot"
    assert captured["inputs"]["repo"] == "owner/repo"
    assert captured["inputs"]["issue"] == 7
    assert captured["inputs"]["issue_number"] == 7
    assert captured["inputs"]["pr"] == 9
    assert captured["inputs"]["pr_number"] == 9
    assert captured["inputs"]["branch"] == "ai/fix/7"
    assert captured["inputs"]["live"] is False
    assert captured["inputs"]["foo"] == "bar"


def test_run_path_materializes_full_package_for_fala(monkeypatch, tmp_path):
    from lokay import graph_run

    monkeypatch.setattr(
        "fala.host_run_package",
        lambda **_kwargs: {
            "ok": True,
            "run_status": "completed",
            "effector_results": {
                "reduce_status_snapshot": {
                    "status": "completed",
                    "output": {"values": {"ok": True, "health": "idle"}},
                }
            },
        },
    )
    result = graph_run.run_path(
        path_id="status_snapshot",
        repo="local/status",
        package_path=graph_run.find_default_package(),
        db_path=tmp_path,
        require_healthy=False,
    )
    pkg = Path(result["package"]).read_text(encoding="utf-8")
    assert pkg.count("[[correlation_paths]]") > 1
    assert 'id = "status_snapshot"' in pkg
    assert 'id = "factory_pass"' in pkg
    assert 'id = "executor_row"' in pkg
    assert "PLACEHOLDER_PROJECT" not in pkg


def test_issue_journal_dir_isolates_coding_execution(tmp_path):
    from lokay.graph_run import issue_journal_dir

    first = issue_journal_dir("coding_execution", "Temida/Temida", 4999, home=tmp_path)
    second = issue_journal_dir("coding_execution", "Temida/Temida", 4996, home=tmp_path)
    shared = tmp_path / ".lokay" / "fala"
    assert first is not None and second is not None
    assert first != second
    assert first.parent.name == "coding-execution"
    assert str(shared) not in {str(first), str(second)}
    assert issue_journal_dir("localize_execution", "Temida/Temida", 4999, home=tmp_path) is None


def test_issue_journal_dir_isolates_test_local_execution(tmp_path):
    from lokay.graph_run import issue_journal_dir, path_journal_dir

    first = issue_journal_dir("test_local_execution", "mikolaj92/Temida", 5191, home=tmp_path)
    second = issue_journal_dir("test_local_execution", "mikolaj92/Fala", 186, home=tmp_path)
    shared = path_journal_dir("test_local_execution", "local/test", home=tmp_path)
    assert first is not None and second is not None
    assert first != second
    assert first.parent.name == "test-local-execution"
    assert first != shared
    assert "5191" in str(first)
    assert "186" in str(second)


def test_pr_journal_dir_isolates_pr_triage(tmp_path):
    from lokay.graph_run import pr_journal_dir, path_journal_dir, issue_journal_dir

    first = pr_journal_dir("pr_triage", "mikolaj92/Fala", 187, home=tmp_path)
    second = pr_journal_dir("pr_triage", "mikolaj92/Temida", 5195, home=tmp_path)
    shared = path_journal_dir("pr_triage", home=tmp_path)
    repair = pr_journal_dir("pr_repair", "mikolaj92/Fala", 187, home=tmp_path)
    assert first is not None and second is not None
    assert first != second
    assert first.parent.name == "pr-triage"
    assert repair.parent.name == "pr-repair"
    assert first != shared
    assert "187" in str(first)
    assert "5195" in str(second)
    assert issue_journal_dir("pr_triage", "mikolaj92/Fala", 186, home=tmp_path) is None
    nested = path_journal_dir("pr_triage", "mikolaj92/Fala", pr=187, home=tmp_path)
    assert nested == first


def test_path_journal_dir_isolates_child_packages(tmp_path):
    from lokay.graph_run import path_journal_dir, _materialize_package

    shared = tmp_path / ".lokay" / "fala"
    status = path_journal_dir("status_snapshot", home=tmp_path)
    executor = path_journal_dir("executor_row", home=tmp_path)
    assert status == shared / "status_snapshot"
    assert executor == shared / "executor_row"
    assert status != executor
    src = tmp_path / "pkg.toml"
    src.write_text(
        'version = "2"\n'
        "[[correlation_paths]]\n"
        'id = "status_snapshot"\n'
        "[[correlation_paths]]\n"
        'id = "executor_row"\n'
        'command = ["uv", "run", "--project", "PLACEHOLDER_PROJECT"]\n',
        encoding="utf-8",
    )
    project = tmp_path / "checkout"
    project.mkdir()
    _materialize_package(src, status / "lokay.fala-package.toml", project=project)
    _materialize_package(src, executor / "lokay.fala-package.toml", project=project)
    status_pkg = (status / "lokay.fala-package.toml").read_text(encoding="utf-8")
    executor_pkg = (executor / "lokay.fala-package.toml").read_text(encoding="utf-8")
    assert 'id = "status_snapshot"' in status_pkg
    assert 'id = "executor_row"' in status_pkg
    assert 'id = "status_snapshot"' in executor_pkg
    assert 'id = "executor_row"' in executor_pkg
    assert str(project.resolve()) in status_pkg
    assert "PLACEHOLDER_PROJECT" not in status_pkg
    assert not (shared / "lokay.fala-package.toml").exists()
    assert path_journal_dir(
        "coding_execution", "Temida/Temida", 4999, home=tmp_path
    ).parent.name == "coding-execution"


def test_shared_fala_root_db_path_is_remapped(tmp_path):
    from lokay import graph_run

    shared = tmp_path / ".lokay" / "fala"
    work = graph_run.path_journal_dir("status_snapshot", home=tmp_path)
    assert work != shared
    assert graph_run._is_shared_fala_root(shared, home=tmp_path)
    assert not graph_run._is_shared_fala_root(work, home=tmp_path)


def test_run_path_does_not_clobber_shared_package(tmp_path, monkeypatch):
    from lokay import graph_run

    monkeypatch.setattr(graph_run.Path, "home", classmethod(lambda cls: tmp_path))
    shared = tmp_path / ".lokay" / "fala"
    shared.mkdir(parents=True)
    marker = 'id = "full-catalog"\n'
    (shared / "lokay.fala-package.toml").write_text(marker, encoding="utf-8")

    def host(**kwargs):
        return {
            "ok": True,
            "run_status": "completed",
            "effector_results": {
                "reduce_status_snapshot": {
                    "status": "completed",
                    "output": {"values": {"ok": True, "health": "idle"}},
                }
            },
        }

    monkeypatch.setattr("fala.host_run_package", host)
    result = graph_run.run_path(
        path_id="status_snapshot",
        repo="local/status",
        package_path=graph_run.find_default_package(),
        live=False,
        require_healthy=False,
    )
    isolated = shared / "status_snapshot" / "lokay.fala-package.toml"
    assert result["package"] == str(isolated)
    assert (shared / "lokay.fala-package.toml").read_text(encoding="utf-8") == marker
    materialized = isolated.read_text(encoding="utf-8")
    assert 'id = "status_snapshot"' in materialized
    assert 'id = "executor_row"' in materialized
    assert materialized.count("[[correlation_paths]]") > 1



def test_run_path_supplies_project_root_for_fala_inherit_env(
    monkeypatch, tmp_path
):
    import os
    from lokay import graph_run

    monkeypatch.delenv("LOKAY_ROOT", raising=False)
    seen = {}

    def host(**_kwargs):
        seen["root"] = os.environ.get("LOKAY_ROOT")
        return {"ok": True, "run_status": "completed", "effector_results": {}}

    monkeypatch.setattr("fala.host_run_package", host)
    graph_run.run_path(
        path_id="status_snapshot",
        repo="local/status",
        package_path=graph_run.find_default_package(),
        db_path=tmp_path,
        require_healthy=False,
    )

    assert seen["root"] == str(graph_run._project_root())


def test_run_path_restores_dynamic_library_environment(monkeypatch, tmp_path):
    import os
    from lokay import graph_run

    monkeypatch.setenv("DYLD_LIBRARY_PATH", "/operator/lib")

    def host(**_kwargs):
        os.environ["DYLD_LIBRARY_PATH"] = "/fala/native"
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = "/fala/fallback"
        return {"ok": True, "run_status": "completed", "effector_results": {}}

    monkeypatch.setattr("fala.host_run_package", host)
    graph_run.run_path(
        path_id="status_snapshot",
        repo="local/status",
        package_path=graph_run.find_default_package(),
        db_path=tmp_path,
        require_healthy=False,
    )

    assert os.environ["DYLD_LIBRARY_PATH"] == "/operator/lib"
    assert "DYLD_FALLBACK_LIBRARY_PATH" not in os.environ
