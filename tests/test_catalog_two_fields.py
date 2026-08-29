"""Catalog composes task with code. Two fields. No separate PR field."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lokay.catalog import (
    CATALOG_FIELDS,
    CatalogBinding,
    CatalogError,
    CatalogRow,
    KNOWN_PLUGINS,
    compose_catalog,
    parse_catalog_row,
)
from lokay.config import RepoConfig, load_config


def _clear_mill_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "LOKAY_MODE",
        "LOKAY_EXECUTOR_ENABLED",
        "LOKAY_AGENT",
        "LOKAY_MERGE_ENABLED",
        "LOKAY_REQUIRE_CHECKS",
        "LOKAY_CONFIG",
    ):
        monkeypatch.delenv(key, raising=False)


def test_old_row_is_github_plus_github() -> None:
    row = parse_catalog_row(
        {"name": "mikolaj92/lokay", "clone_path": "/Users/mikomac/Developer/OSS/lokay"}
    )
    assert row.issues == CatalogBinding("github", "mikolaj92/lokay")
    assert row.code == CatalogBinding("github", "mikolaj92/lokay")
    assert row.issues.plugin == row.code.plugin == "github"
    assert row.issues.target == row.code.target == "mikolaj92/lokay"
    assert row.name == "mikolaj92/lokay"


def test_mixed_jira_bitbucket_keeps_two_targets() -> None:
    row = parse_catalog_row(
        {
            "issues": {"plugin": "jira", "target": "PROJ"},
            "code": {
                "plugin": "bitbucket",
                "target": "workspace/repo",
                "clone_path": "/tmp/repo",
            },
        }
    )
    assert row.issues == CatalogBinding("jira", "PROJ")
    assert row.code == CatalogBinding("bitbucket", "workspace/repo")
    assert (row.issues.plugin, row.issues.target) != (row.code.plugin, row.code.target)
    composed = compose_catalog(row.issues, row.code)
    assert composed.issues.target == "PROJ"
    assert composed.code.target == "workspace/repo"


def test_no_separate_pr_field() -> None:
    assert CATALOG_FIELDS == ("issues", "code")
    assert "prs" not in CATALOG_FIELDS
    assert "prs" not in CatalogRow.__dataclass_fields__
    row = parse_catalog_row({"name": "mikolaj92/lokay", "clone_path": "/tmp/lokay"})
    assert not hasattr(row, "prs")
    with pytest.raises(CatalogError, match="no separate prs field"):
        parse_catalog_row(
            {
                "name": "mikolaj92/lokay",
                "clone_path": "/tmp/lokay",
                "prs": {"plugin": "github", "target": "mikolaj92/lokay"},
            }
        )
    with pytest.raises(CatalogError, match="no separate prs field"):
        parse_catalog_row(
            {
                "name": "mikolaj92/lokay",
                "code": {
                    "plugin": "github",
                    "target": "mikolaj92/lokay",
                    "clone_path": "/tmp/lokay",
                    "prs": {"plugin": "github"},
                },
            }
        )


def test_thirty_current_rows_work_without_hand_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_mill_env(monkeypatch)
    root = Path(__file__).resolve().parents[1]
    catalog = root / "repos.mikolaj92.yaml"
    raw = yaml.safe_load(catalog.read_text(encoding="utf-8")) or {}
    entries = list(raw.get("repos") or [])
    assert len(entries) >= 30
    assert all("issues" not in entry and "code" not in entry for entry in entries)

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"mode: dry-run\nrepos_file: {catalog}\n",
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    assert len(cfg.repos) == len(entries)
    for repo in cfg.repos:
        assert repo.issues is not None and repo.code is not None
        assert repo.issues.plugin == "github"
        assert repo.code.plugin == "github"
        assert repo.issues.target == repo.code.target == repo.name
        assert "/" in repo.name
        assert not hasattr(repo, "prs")


def test_unknown_plugin_fails_at_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_mill_env(monkeypatch)
    path = tmp_path / "bad.yaml"
    path.write_text(
        f"""
mode: dry-run
repos:
  - name: a/b
    clone_path: {tmp_path}
    issues: {{ plugin: jira, target: PROJ }}
    code: {{ plugin: github, target: a/b }}
""",
        encoding="utf-8",
    )
    with pytest.raises(CatalogError, match="unknown catalog plugin 'jira'"):
        load_config(path)
    assert "jira" not in KNOWN_PLUGINS
    assert "bitbucket" not in KNOWN_PLUGINS
    assert "github" in KNOWN_PLUGINS
    assert "azure" in KNOWN_PLUGINS


def test_explicit_github_and_azure_rows_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_mill_env(monkeypatch)
    path = tmp_path / "mixed.yaml"
    path.write_text(
        f"""
mode: dry-run
repos:
  - issues: {{ plugin: github, target: mikolaj92/reviewkit }}
    code: {{ plugin: github, target: mikolaj92/reviewkit, clone_path: {tmp_path / "rk"} }}
  - issues: {{ plugin: azure, target: org/project }}
    code: {{ plugin: azure, target: org/project/repo, clone_path: {tmp_path / "az"} }}
""",
        encoding="utf-8",
    )
    cfg = load_config(path)
    by_plugin = {repo.issues.plugin: repo for repo in cfg.repos}
    gh, az = by_plugin["github"], by_plugin["azure"]
    assert gh.name == "mikolaj92/reviewkit"
    assert gh.issues == CatalogBinding("github", "mikolaj92/reviewkit")
    assert gh.code == CatalogBinding("github", "mikolaj92/reviewkit")
    assert az.issues == CatalogBinding("azure", "org/project")
    assert az.code == CatalogBinding("azure", "org/project/repo")
    assert az.issues.target != az.code.target


def test_repo_config_defaults_github_and_parent_keeps_name() -> None:
    repo = RepoConfig(name="mikolaj92/lokay", clone_path=Path("/tmp/lokay"))
    assert repo.name == "mikolaj92/lokay"
    assert repo.issues == CatalogBinding("github", "mikolaj92/lokay")
    assert repo.code == CatalogBinding("github", "mikolaj92/lokay")
    assert not hasattr(repo, "prs")


def test_catalog_module_has_no_adapters_or_gh() -> None:
    text = (
        Path(__file__).resolve().parents[1] / "src" / "lokay" / "catalog.py"
    ).read_text(encoding="utf-8")
    for token in (
        "gh_issues",
        "gh_prs",
        "from lokay.gh",
        "class GitHub",
        "def list_open",
    ):
        assert token not in text, token
