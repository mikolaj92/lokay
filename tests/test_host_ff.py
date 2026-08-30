"""Mill host fetch + ff-only onto origin/main, or fail-closed."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lokay.git_host_ff import (
    fast_forward_origin_main,
    origin_is_github_lokay,
    origin_is_lokay,
)
from lokay.graph_run import describe_package
from lokay.proc import host_ff
from lokay.runner import Runner


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def _identity(cwd: Path) -> None:
    _git(cwd, "config", "user.email", "lokay@test")
    _git(cwd, "config", "user.name", "lokay-test")
    _git(cwd, "config", "commit.gpgsign", "false")


def _pair(tmp_path: Path) -> tuple[Path, Path]:
    """Bare origin named mikolaj92/lokay.git plus a host clone on main."""
    upstream = tmp_path / "mikolaj92" / "lokay.git"
    upstream.parent.mkdir(parents=True)
    _git(tmp_path, "init", "--bare", "-b", "main", str(upstream))
    seed = tmp_path / "seed"
    _git(tmp_path, "clone", str(upstream), str(seed))
    _identity(seed)
    (seed / "README").write_text("base\n", encoding="utf-8")
    (seed / "repos.mikolaj92.yaml").write_text("repos: []\n", encoding="utf-8")
    (seed / ".lokay").mkdir()
    (seed / ".lokay" / "approach.md").write_text("plan\n", encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-m", "init")
    _git(seed, "push", "origin", "main")
    host = tmp_path / "host"
    _git(tmp_path, "clone", str(upstream), str(host))
    _identity(host)
    return seed, host


def _advance_origin(seed: Path, text: str) -> None:
    (seed / "README").write_text(text, encoding="utf-8")
    _git(seed, "add", "README")
    _git(seed, "commit", "-m", "advance")
    _git(seed, "push", "origin", "main")


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_origin_is_lokay_accepts_canonical_and_local_path():
    assert origin_is_lokay("git@github.com:mikolaj92/lokay.git")
    assert origin_is_lokay("https://github.com/mikolaj92/lokay")
    assert origin_is_lokay("/tmp/mikolaj92/lokay.git")
    assert not origin_is_lokay("git@github.com:mikolaj92/temida.git")


def test_origin_is_github_lokay_rejects_local_clone():
    assert origin_is_github_lokay("git@github.com:mikolaj92/lokay.git")
    assert origin_is_github_lokay("https://github.com/mikolaj92/lokay")
    assert origin_is_github_lokay("ssh://git@github.com/mikolaj92/lokay")
    assert not origin_is_github_lokay("/tmp/mikolaj92/lokay.git")


def test_ff_only_when_behind_and_clean(tmp_path: Path):
    seed, host = _pair(tmp_path)
    old = _git(host, "rev-parse", "HEAD").stdout.strip()
    _advance_origin(seed, "new\n")
    remote = _git(seed, "rev-parse", "HEAD").stdout.strip()
    assert old != remote

    result = fast_forward_origin_main(Runner(), host)
    assert result["updated"] is True
    assert _git(host, "rev-parse", "HEAD").stdout.strip() == remote
    assert (host / "README").read_text(encoding="utf-8") == "new\n"


def test_clean_issue_branch_returns_to_main_and_fast_forwards(tmp_path: Path):
    seed, host = _pair(tmp_path)
    _git(host, "checkout", "-b", "ai/fix/361-host-ff")
    _advance_origin(seed, "new\n")
    remote = _git(seed, "rev-parse", "HEAD").stdout.strip()

    result = fast_forward_origin_main(Runner(), host)

    assert result["updated"] is True
    assert _git(host, "branch", "--show-current").stdout.strip() == "main"
    assert _git(host, "rev-parse", "HEAD").stdout.strip() == remote
    assert (host / "README").read_text(encoding="utf-8") == "new\n"


def test_harvest_dirty_host_branch_returns_to_main_and_fast_forwards(tmp_path: Path):
    seed, host = _pair(tmp_path)
    _git(host, "checkout", "-b", "ai/fix/386-host-ff")
    _advance_origin(seed, "new\n")
    remote = _git(seed, "rev-parse", "HEAD").stdout.strip()
    (host / ".lokay" / "approach.md").write_text("harvest plan\n", encoding="utf-8")
    (host / "tests").mkdir()
    (host / "tests" / "test_other_tick.py").write_text(
        "assert True\n", encoding="utf-8"
    )

    result = fast_forward_origin_main(Runner(), host)

    assert result["updated"] is True
    assert _git(host, "branch", "--show-current").stdout.strip() == "main"
    assert _git(host, "rev-parse", "HEAD").stdout.strip() == remote
    assert (host / ".lokay" / "approach.md").read_text(encoding="utf-8") == "plan\n"
    assert not (host / "tests" / "test_other_tick.py").exists()
    assert _git(host, "status", "--porcelain").stdout == ""


def test_dirty_linked_issue_worktree_is_refused_without_checkout(tmp_path: Path):
    seed, host = _pair(tmp_path)
    issue_worktree = tmp_path / "live-issue-worktree"
    _git(host, "worktree", "add", "-b", "ai/fix/386-live", str(issue_worktree))
    _advance_origin(seed, "new\n")
    (issue_worktree / ".lokay" / "approach.md").write_text(
        "live writer plan\n", encoding="utf-8"
    )

    try:
        fast_forward_origin_main(Runner(), issue_worktree)
        raise AssertionError("live issue worktree must fail closed")
    except RuntimeError as exc:
        assert "dirty" in str(exc)
    assert (
        _git(issue_worktree, "branch", "--show-current").stdout.strip()
        == "ai/fix/386-live"
    )
    assert (issue_worktree / ".lokay" / "approach.md").read_text(
        encoding="utf-8"
    ) == "live writer plan\n"


def test_dirty_issue_branch_is_refused_without_checkout(tmp_path: Path):
    seed, host = _pair(tmp_path)
    _git(host, "checkout", "-b", "ai/fix/361-host-ff")
    _advance_origin(seed, "new\n")
    (host / "README").write_text("local dirty\n", encoding="utf-8")

    try:
        fast_forward_origin_main(Runner(), host)
        raise AssertionError("dirty issue checkout must fail closed")
    except RuntimeError as exc:
        assert "dirty" in str(exc)
    assert _git(host, "branch", "--show-current").stdout.strip() == "ai/fix/361-host-ff"
    assert (host / "README").read_text(encoding="utf-8") == "local dirty\n"


def test_refuse_when_behind_and_dirty(tmp_path: Path):
    seed, host = _pair(tmp_path)
    old = _git(host, "rev-parse", "HEAD").stdout.strip()
    _advance_origin(seed, "new\n")
    (host / "README").write_text("local dirty\n", encoding="utf-8")

    try:
        fast_forward_origin_main(Runner(), host)
        raise AssertionError("dirty behind checkout must fail closed")
    except RuntimeError as exc:
        assert "dirty" in str(exc)
    assert _git(host, "rev-parse", "HEAD").stdout.strip() == old
    assert (host / "README").read_text(encoding="utf-8") == "local dirty\n"


def test_skip_worktree_catalog_is_preserved_on_unrelated_ff(tmp_path: Path):
    seed, host = _pair(tmp_path)
    local = "clone_path: /Users/mini-m4-main/Developer\n"
    (host / "repos.mikolaj92.yaml").write_text(local, encoding="utf-8")
    _git(host, "update-index", "--skip-worktree", "--", "repos.mikolaj92.yaml")
    _advance_origin(seed, "new\n")

    result = fast_forward_origin_main(Runner(), host)
    assert result["updated"] is True
    assert (host / "repos.mikolaj92.yaml").read_text(encoding="utf-8") == local
    listed = _git(host, "ls-files", "-v", "--", "repos.mikolaj92.yaml").stdout
    assert listed.startswith("S ") or listed.startswith("s ")


def test_skip_worktree_product_config_fast_forwards(tmp_path: Path):
    """Product config is mill policy, not a host catalog. origin/main must land."""
    seed, host = _pair(tmp_path)
    (seed / "config.yaml").write_text("require_llm_review: false\n", encoding="utf-8")
    _git(seed, "add", "config.yaml")
    _git(seed, "commit", "-m", "config")
    _git(seed, "push", "origin", "main")
    fast_forward_origin_main(Runner(), host)

    _git(host, "update-index", "--skip-worktree", "--", "config.yaml")
    (seed / "config.yaml").write_text("require_llm_review: true\n", encoding="utf-8")
    _git(seed, "add", "config.yaml")
    _git(seed, "commit", "-m", "reviewer")
    _git(seed, "push", "origin", "main")
    remote = _git(seed, "rev-parse", "HEAD").stdout.strip()

    result = fast_forward_origin_main(Runner(), host)

    assert result["updated"] is True
    assert _git(host, "rev-parse", "HEAD").stdout.strip() == remote
    assert (host / "config.yaml").read_text(
        encoding="utf-8"
    ) == "require_llm_review: true\n"
    listed = _git(host, "ls-files", "-v", "--", "config.yaml").stdout
    assert listed.startswith("H ") or listed.startswith("h ")


def test_refuse_when_skip_worktree_would_be_overwritten(tmp_path: Path):
    seed, host = _pair(tmp_path)
    local = "clone_path: /Users/mini-m4-main/Developer\n"
    (host / "repos.mikolaj92.yaml").write_text(local, encoding="utf-8")
    _git(host, "update-index", "--skip-worktree", "--", "repos.mikolaj92.yaml")
    old = _git(host, "rev-parse", "HEAD").stdout.strip()

    (seed / "repos.mikolaj92.yaml").write_text(
        "clone_path: /Users/laptop\n", encoding="utf-8"
    )
    _git(seed, "add", "repos.mikolaj92.yaml")
    _git(seed, "commit", "-m", "laptop paths")
    _git(seed, "push", "origin", "main")

    try:
        fast_forward_origin_main(Runner(), host)
        raise AssertionError("skip-worktree overwrite must fail closed")
    except RuntimeError as exc:
        assert "skip-worktree" in str(exc)
    assert _git(host, "rev-parse", "HEAD").stdout.strip() == old
    assert (host / "repos.mikolaj92.yaml").read_text(encoding="utf-8") == local


def test_already_current_is_ok(tmp_path: Path):
    _seed, host = _pair(tmp_path)
    result = fast_forward_origin_main(Runner(), host)
    assert result["updated"] is False
    assert result["already_current"] is True


def test_caretaker_fetch_skips_second_git_fetch(tmp_path: Path, monkeypatch):
    seed, host = _pair(tmp_path)
    current = fast_forward_origin_main(Runner(), host)
    _advance_origin(seed, "next\n")
    monkeypatch.setenv("LOKAY_HOST_FF_FETCHED", "1")
    skipped = fast_forward_origin_main(Runner(), host)
    assert skipped["already_current"] is True
    assert skipped["head"] == current["head"]
    monkeypatch.delenv("LOKAY_HOST_FF_FETCHED")
    moved = fast_forward_origin_main(Runner(), host)
    assert moved["updated"] is True
    assert moved["head"] != current["head"]


def test_github_sha_match_skips_git_fetch(tmp_path: Path, monkeypatch):
    seed, host = _pair(tmp_path)
    current = fast_forward_origin_main(Runner(), host)
    remote = _git(host, "rev-parse", "origin/main").stdout.strip()
    monkeypatch.setattr("lokay.git_host_ff.origin_is_github_lokay", lambda url: True)
    monkeypatch.setattr("lokay.git_host_ff.github_main_sha", lambda runner: remote)
    fetched: list[tuple[str, ...]] = []
    real = Runner.run_checked

    def wrapped(self, spec, *, live):
        if spec.argv[:3] == ("git", "fetch", "origin"):
            fetched.append(spec.argv)
        return real(self, spec, live=live)

    monkeypatch.setattr(Runner, "run_checked", wrapped)
    skipped = fast_forward_origin_main(Runner(), host)
    assert skipped["already_current"] is True
    assert skipped["head"] == current["head"]
    assert fetched == []


def test_github_sha_mismatch_still_fetches(tmp_path: Path, monkeypatch):
    seed, host = _pair(tmp_path)
    current = fast_forward_origin_main(Runner(), host)
    _advance_origin(seed, "next\n")
    new_remote = _git(seed, "rev-parse", "HEAD").stdout.strip()
    monkeypatch.setattr("lokay.git_host_ff.origin_is_github_lokay", lambda url: True)
    monkeypatch.setattr("lokay.git_host_ff.github_main_sha", lambda runner: new_remote)
    moved = fast_forward_origin_main(Runner(), host)
    assert moved["updated"] is True
    assert moved["head"] != current["head"]


def test_github_sha_probe_failure_still_fetches(tmp_path: Path, monkeypatch):
    seed, host = _pair(tmp_path)
    current = fast_forward_origin_main(Runner(), host)
    _advance_origin(seed, "next\n")
    monkeypatch.setattr("lokay.git_host_ff.origin_is_github_lokay", lambda url: True)
    monkeypatch.setattr("lokay.git_host_ff.github_main_sha", lambda runner: "")
    moved = fast_forward_origin_main(Runner(), host)
    assert moved["updated"] is True
    assert moved["head"] != current["head"]


def test_host_ff_payload_tells_caretaker_whether_head_moved(tmp_path: Path):
    seed, host = _pair(tmp_path)
    current = fast_forward_origin_main(Runner(), host)
    assert current["updated"] is False
    assert current["already_current"] is True
    _advance_origin(seed, "next\n")
    moved = fast_forward_origin_main(Runner(), host)
    assert moved["updated"] is True
    assert moved["already_current"] is False
    assert moved["head"]
    assert moved["head"] != current["head"]


def test_cli_planned_without_live(tmp_path: Path, capsys):
    _seed, host = _pair(tmp_path)
    code = host_ff.main(["--checkout", str(host)])
    payload = _payload(capsys)
    assert code == 0
    assert payload["ok"] is True
    assert payload["planned"] is True


def test_cli_live_ff_when_behind(tmp_path: Path, capsys):
    seed, host = _pair(tmp_path)
    _advance_origin(seed, "new\n")
    remote = _git(seed, "rev-parse", "HEAD").stdout.strip()
    code = host_ff.main(["--checkout", str(host), "--live"])
    payload = _payload(capsys)
    assert code == 0
    assert payload["ok"] is True
    assert payload["updated"] is True
    assert payload["head"] == remote


def test_snapshot_process_head_sets_once(monkeypatch, tmp_path: Path):
    from lokay.git_host_ff import PROCESS_HEAD_ENV, snapshot_process_head

    monkeypatch.delenv(PROCESS_HEAD_ENV, raising=False)
    monkeypatch.setattr("lokay.git_host_ff.checkout_head", lambda path: "abc")
    assert snapshot_process_head(tmp_path) == "abc"
    monkeypatch.setattr("lokay.git_host_ff.checkout_head", lambda path: "def")
    assert snapshot_process_head(tmp_path) == "abc"
    assert snapshot_process_head(tmp_path, refresh=True) == "def"


def test_process_head_moved_when_env_differs(monkeypatch, tmp_path: Path):
    from lokay.git_host_ff import PROCESS_HEAD_ENV, process_head_moved

    monkeypatch.setenv(PROCESS_HEAD_ENV, "abc")
    monkeypatch.setattr("lokay.git_host_ff.checkout_head", lambda path: "def")
    moved = process_head_moved(tmp_path)
    assert moved is not None
    assert moved["reason"] == "host_updated"
    assert moved["process_head"] == "abc"
    assert moved["head"] == "def"
    monkeypatch.setattr("lokay.git_host_ff.checkout_head", lambda path: "abc")
    assert process_head_moved(tmp_path) is None


def test_factory_begin_host_gate_refuses_in_cycle_update():
    from lokay.proc.gate_factory_begin_host import gate

    out = gate(
        {"updated": True, "head": "a", "origin_main": "b"}, live=True, checkout=""
    )
    assert out["ok"] is True and out["route"] == "restart"
    assert out["reason"] == "host_updated"


def test_factory_begin_host_gate_continues_current():
    from lokay.proc.gate_factory_begin_host import gate

    assert gate({"updated": False}, live=True, checkout="")["route"] == "begin"


def test_factory_begin_planned_ignores_host_updated():
    from lokay.proc.gate_factory_begin_host import gate

    assert gate({"updated": True}, live=False, checkout="")["route"] == "begin"


def test_factory_pass_starts_with_begin_then_product_children():
    desc = describe_package()
    path = next(p for p in desc["paths"] if p["id"] == "factory_pass")
    ids = [n["id"] for n in path["nodes"]]
    assert ids[:4] == [
        "host_ff",
        "factory_begin_host_gate",
        "factory_begin",
        "reap_stale_worktrees",
    ]


def test_department_selects_skip_on_host_restart():
    from lokay.organ.departments_boundary import handle_departments

    up = {"factory_begin_host_gate": {"route": "restart"}}
    ctx = {"cfg": [], "live": []}
    for atom in (
        "select_self_repair_department",
        "select_issue_triage_department",
        "select_executor_department",
        "select_pr_triage_department",
        "select_pr_repair_department",
    ):
        out = handle_departments(atom, {}, up, ctx)
        assert out["route"] == "skip"
        assert out["reason"] == "host_updated"
