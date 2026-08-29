"""LLM slot writes an artifact and structured output. It does not persist."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from types import SimpleNamespace

from lokay.agent import run_agent
from lokay.config import Config
from lokay.runner import CommandSpec


ROOT = Path(__file__).resolve().parents[1]
LLM_SLOT = (
    ROOT / "src" / "lokay" / "agent.py",
    ROOT / "src" / "lokay" / "proc" / "run_agent.py",
)
_FORBIDDEN = ("git commit", "commit_all", "git_commit")
_READY = frozenset({"implemented", "repaired"})
PI_ARGS = [
    "-p",
    "{prompt}",
    "--model",
    "{model}",
    "--approve",
    "--session-id",
    "{session}",
]


def _package() -> dict:
    return tomllib.loads(
        (ROOT / "fala" / "lokay.fala-package.toml").read_text(encoding="utf-8")
    )


def test_llm_slot_source_never_persists_a_revision() -> None:
    hits = []
    for path in LLM_SLOT:
        text = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN:
            if token in text:
                hits.append(f"{path.relative_to(ROOT)}: {token}")
    assert hits == []


def test_run_agent_timeout_is_ok_structured_state(monkeypatch, capsys, tmp_path) -> None:
    from lokay.proc import run_agent as proc

    monkeypatch.setattr(proc, "load_cfg", lambda _args: object())
    monkeypatch.setattr(proc, "agent_execute_allowed", lambda cfg, live_flag: True)
    monkeypatch.setattr(proc, "runner", lambda: object())
    monkeypatch.setattr(
        proc,
        "run_agent",
        lambda *_a, **_k: {
            "timed_out": True,
            "status": "failed",
            "returncode": 124,
            "agent": "pi",
            "worktree": str(tmp_path),
        },
    )

    def boom(*_a, **_k):
        raise AssertionError("LLM slot must not persist a revision")

    import lokay.git_commit as git_commit

    monkeypatch.setattr(git_commit, "commit_all", boom)
    assert not hasattr(proc, "commit_all")

    rc = proc.main(["--worktree", str(tmp_path), "--prompt", "implement"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "timeout"
    assert payload["reason"] == "timeout"
    assert payload.get("committed") is not True


def test_agent_execute_timeout_invokes_only_the_harness(tmp_path: Path) -> None:
    class Rec:
        def __init__(self) -> None:
            self.specs: list[CommandSpec] = []

        def run(self, spec: CommandSpec, *, live: bool):
            self.specs.append(spec)
            return SimpleNamespace(
                returncode=124, stdout="", stderr="", timed_out=True
            )

    runner = Rec()
    cfg = Config(
        agent="pi",
        agent_command="pi",
        agent_args=list(PI_ARGS),
        executor_enabled=True,
        timeout_seconds=1,
    )
    out = run_agent(runner, cfg, worktree=tmp_path, prompt="x", execute=True)
    assert out["timed_out"] is True
    assert len(runner.specs) == 1
    argv = list(runner.specs[0].argv)
    assert argv[0] == "pi"
    assert "commit" not in argv
    assert not any("commit_all" in str(part) for part in argv)


def test_coding_execution_llm_slot_has_no_persist_atom() -> None:
    path = next(p for p in _package()["correlation_paths"] if p["id"] == "coding_execution")
    atoms = [(n["id"], (n.get("config") or {}).get("atom")) for n in path["effectors"]]
    assert "run_agent" in {node_id for node_id, _atom in atoms}
    assert all(atom != "commit_all" for _node_id, atom in atoms)


def test_commit_all_is_separate_atom_after_ready_verdict() -> None:
    commit_atoms = []
    run_agent_atoms = []
    for path in _package()["correlation_paths"]:
        for node in path.get("effectors") or []:
            atom = (node.get("config") or {}).get("atom")
            if atom == "commit_all":
                commit_atoms.append((path["id"], node["id"], node.get("when") or {}))
            if node["id"] == "run_agent" or atom == "run_agent":
                run_agent_atoms.append((path["id"], node["id"], atom))
    assert commit_atoms
    assert run_agent_atoms
    assert all(atom != "commit_all" for _path, _nid, atom in run_agent_atoms)
    for path_id, node_id, when in commit_atoms:
        assert when.get("equals") in _READY, (path_id, node_id, when)
        assert node_id != "run_agent"
