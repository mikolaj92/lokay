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


def test_slice_package_unknown_path():
    from lokay.graph_run import _slice_package_to_path

    try:
        _slice_package_to_path('version = "2"\n[[correlation_paths]]\nid = "x"\n', "nope")
    except ValueError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("expected ValueError")


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


def test_path_journal_dir_isolates_sliced_children(tmp_path):
    from lokay.graph_run import path_journal_dir, _slice_package_to_path, _materialize_package

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
        'id = "executor_row"\n',
        encoding="utf-8",
    )
    project = tmp_path / "checkout"
    project.mkdir()
    _materialize_package(src, status / "lokay.fala-package.toml", project=project, path_id="status_snapshot")
    _materialize_package(src, executor / "lokay.fala-package.toml", project=project, path_id="executor_row")
    status_pkg = (status / "lokay.fala-package.toml").read_text(encoding="utf-8")
    executor_pkg = (executor / "lokay.fala-package.toml").read_text(encoding="utf-8")
    assert 'id = "status_snapshot"' in status_pkg
    assert 'id = "executor_row"' not in status_pkg
    assert 'id = "executor_row"' in executor_pkg
    assert 'id = "status_snapshot"' not in executor_pkg
    assert not (shared / "lokay.fala-package.toml").exists()
    assert path_journal_dir(
        "coding_execution", "Temida/Temida", 4999, home=tmp_path
    ).parent.name == "coding-execution"
    sliced = _slice_package_to_path(src.read_text(encoding="utf-8"), "status_snapshot")
    assert sliced.count("[[correlation_paths]]") == 1


def test_shared_fala_root_db_path_is_remapped(tmp_path):
    from lokay import graph_run

    shared = tmp_path / ".lokay" / "fala"
    work = graph_run.path_journal_dir("status_snapshot", home=tmp_path)
    assert work != shared
    assert graph_run._is_shared_fala_root(shared, home=tmp_path)
    assert not graph_run._is_shared_fala_root(work, home=tmp_path)


def test_run_path_does_not_clobber_shared_sliced_package(tmp_path, monkeypatch):
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
    sliced = isolated.read_text(encoding="utf-8")
    assert 'id = "status_snapshot"' in sliced
    assert 'id = "executor_row"' not in sliced

