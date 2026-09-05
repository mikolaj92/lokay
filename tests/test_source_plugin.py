"""One catalog source plugin owns observations without a local source mirror."""

from pathlib import Path

import pytest

from lokay.catalog import CatalogBinding, CatalogError
from lokay.config import RepoConfig
from lokay.source import issue_from_task, load_code, load_source, load_tasks
from lokay.tasks import Task


def row(plugin: str = "azure") -> RepoConfig:
    return RepoConfig(
        name="product/repo",
        clone_path=Path("/tmp/repo"),
        issues=CatalogBinding(plugin, "org/project"),
        code=CatalogBinding(plugin, "org/project/repo"),
    )


def test_source_task_observation_keeps_logical_catalog_identity():
    task = Task(plugin="azure", target="org/project", number=42, state="OPEN")
    issue = issue_from_task(task, repo="product/repo")
    assert issue.repo == "product/repo"
    assert issue.number == 42
    assert issue.url == ""


def test_source_contract_binds_task_and_code_blocks_from_one_plugin(monkeypatch):
    source_row = row()
    tasks = type("Tasks", (), {"plugin": "azure"})()
    code = type("Code", (), {"target": type("Target", (), {"plugin": "azure"})()})()
    monkeypatch.setattr("lokay.source.load_tasks", lambda *_a, **_k: tasks)
    monkeypatch.setattr("lokay.source.load_code", lambda *_a, **_k: code)

    source = load_source(source_row, runner=object(), config=object(), live=False)
    assert source.plugin == "azure"
    assert source.tasks is tasks
    assert source.code is code


def test_source_loader_rejects_vendor_split_before_loading_any_block():
    split = RepoConfig(
        name="product/repo",
        clone_path=Path("/tmp/repo"),
        issues=CatalogBinding("github", "owner/issues"),
        code=CatalogBinding("azure", "org/project/repo"),
    )
    with pytest.raises(CatalogError, match="one source plugin"):
        load_tasks(split, runner=object(), config=object(), live=False)
    with pytest.raises(CatalogError, match="one source plugin"):
        load_code(split, runner=object(), config=object(), live=False)
