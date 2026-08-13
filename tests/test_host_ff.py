"""Mill host fetch + ff-only onto origin/main, or fail-closed."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lokay.git_host_ff import fast_forward_origin_main, origin_is_lokay
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


def test_refuse_when_skip_worktree_would_be_overwritten(tmp_path: Path):
    seed, host = _pair(tmp_path)
    local = "clone_path: /Users/mini-m4-main/Developer\n"
    (host / "repos.mikolaj92.yaml").write_text(local, encoding="utf-8")
    _git(host, "update-index", "--skip-worktree", "--", "repos.mikolaj92.yaml")
    old = _git(host, "rev-parse", "HEAD").stdout.strip()

    (seed / "repos.mikolaj92.yaml").write_text("clone_path: /Users/laptop\n", encoding="utf-8")
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


def test_factory_pass_starts_with_host_ff():
    desc = describe_package()
    path = next(p for p in desc["paths"] if p["id"] == "factory_pass")
    ids = [node["id"] for node in path["nodes"]]
    assert ids[0] == "host_ff"
    assert ids[1] == "factory_begin"
    conduction = {node["id"]: node["conduction"] for node in path["nodes"]}
    assert conduction["factory_begin"] == ["host_ff"]
    assert "host_ff" not in conduction["dispatch_implement"]
