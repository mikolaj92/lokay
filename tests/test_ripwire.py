"""Ripwire is optional repo map evidence for triage and coding."""

from __future__ import annotations

import os
from pathlib import Path

from lokay.issue_triage_agent import prompt as triage_prompt
from lokay.models import Issue
from lokay.prompts import issue_fix_prompt
from lokay.ripwire import ranked_paths, repo_map


def _issue() -> Issue:
    return Issue(
        repo="owner/repo",
        number=12,
        title="Bound pass lock to one host",
        body="Keep the lock local.",
        labels=["ai:ready"],
        assignees=["owner"],
        url="https://example.test/issues/12",
    )


def test_missing_ripwire_returns_empty(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir()
    assert repo_map(tmp_path, task="lock") == ""


def test_missing_worktree_returns_empty(tmp_path: Path):
    assert repo_map(tmp_path / "nope", task="lock") == ""


def test_ripwire_for_task_returns_stdout(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "ripwire"
    script.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$*\"\nprintf 'MAP\\n'\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    out = repo_map(repo, task="incremental cache invalidation")
    assert "MAP" in out
    assert "--for=incremental cache invalidation" in out


def test_ripwire_timeout_or_failure_is_empty(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "ripwire"
    script.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    assert repo_map(repo, task="lock") == ""


def test_ranked_paths_extracts_existing_checkout_files(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "src" / "lokay").mkdir(parents=True)
    target = repo / "src" / "lokay" / "preflight.py"
    target.write_text("x\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "ripwire"
    script.write_text(
        "#!/bin/sh\ncat <<'EOF'\n"
        '<f p="./src/lokay/preflight.py"></f>\n'
        '<f p="./missing.py"></f>\n'
        "EOF\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    assert ranked_paths(repo, task="lock") == ("src/lokay/preflight.py",)


def test_map_repo_atom_is_fail_open_and_ranked(tmp_path: Path, monkeypatch):
    from lokay.proc.map_repo import map_repo

    repo = tmp_path / "repo"
    (repo / "src" / "lokay").mkdir(parents=True)
    (repo / "src" / "lokay" / "preflight.py").write_text("x\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "ripwire"
    script.write_text(
        "#!/bin/sh\ncat <<'EOF'\n"
        '<f p="./src/lokay/preflight.py"></f>\n'
        "EOF\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    out = map_repo(
        worktree=str(repo),
        title="Bound pass lock",
        body="Keep the lock local.",
    )
    assert out["ok"] is True
    assert out["route"] == "mapped"
    assert "src/lokay/preflight.py" in out["map"]
    assert out["paths"] == ["src/lokay/preflight.py"]


def test_map_repo_missing_binary_is_empty(tmp_path: Path, monkeypatch):
    from lokay.proc.map_repo import map_repo

    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir()
    out = map_repo(worktree=str(tmp_path), title="lock")
    assert out["ok"] is True
    assert out["route"] == "empty"
    assert out["map"] == ""
    assert out["paths"] == []


def test_map_repo_reads_committed_memory_as_evidence(tmp_path: Path, monkeypatch):
    from lokay.proc.map_repo import map_repo

    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir()
    memory = tmp_path / ".lokay" / "memory"
    memory.mkdir(parents=True)
    (memory / "feature-map.md").write_text("door opens from the hall\n", encoding="utf-8")
    (memory / "paved-path.md").write_text("one hinge, then the latch\n", encoding="utf-8")
    (tmp_path / ".lokay" / "skills").mkdir()
    (tmp_path / ".lokay" / "skills" / "bug.md").write_text("reproduce first\n", encoding="utf-8")
    (tmp_path / ".lokay" / "lessons").mkdir()
    (tmp_path / ".lokay" / "lessons" / "latch.md").write_text("latch was the defect\n", encoding="utf-8")
    out = map_repo(worktree=str(tmp_path), title="door")
    assert out["ok"] is True
    assert out["memory"] == [
        ".lokay/lessons/latch.md",
        ".lokay/memory/feature-map.md",
        ".lokay/memory/paved-path.md",
        ".lokay/skills/bug.md",
    ]
    assert "door opens from the hall" in out["feature_map"]


def test_map_repo_without_memory_does_not_invent_it(tmp_path: Path, monkeypatch):
    from lokay.proc.map_repo import map_repo

    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir()
    out = map_repo(worktree=str(tmp_path), title="door")
    assert out["memory"] == []
    assert out["feature_map"] == ""


def test_prepare_localization_does_not_invoke_ripwire(tmp_path: Path, monkeypatch):
    from lokay.proc.prepare_localization_request import prepare

    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir()
    out = prepare(
        worktree=str(tmp_path),
        repo="owner/repo",
        issue_raw={"title": "Bound pass lock", "body": "Keep the lock local.", "number": 12},
        plan={},
        checks_text="",
        review={},
        extra_paths=["src/lokay/preflight.py"],
        max_paths=40,
        rel_path=".lokay/localize.json",
    )
    assert out["extras"] == ["src/lokay/preflight.py"]


def test_issue_triage_prompt_includes_repo_map():
    text = triage_prompt(
        _issue().to_dict(),
        {"route": "agent"},
        repo_map="<ctx task=\"lock\"/>",
    )
    assert "<ctx task=\"lock\"/>" in text
    assert "Repo map" in text


def test_issue_fix_prompt_includes_repo_map():
    text = issue_fix_prompt(
        _issue(),
        branch="ai/fix/12-x",
        paths=["src/lokay/preflight.py"],
        repo_map="<ctx task=\"lock\"/>",
    )
    assert "<ctx task=\"lock\"/>" in text
    assert "Repo map" in text
