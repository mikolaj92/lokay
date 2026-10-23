from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import cast

from harness2.core.library import Library
from harness2.core.proposer import Proposer
from harness2.core.schedule import run_task
from harness2.core.spec import BenchmarkAdapter, BenchPrompts, BenchSpec, ChannelSpec
from harness2.core.tree import SurfaceSpec, read_tree
from harness2.substrate.base import Install

from lokay import store
from lokay.config import HOME
from lokay.effects import git
from lokay.effects.pi import harness_session, start_harness_run, tick_deadline
from lokay.gates import gate_contract
from lokay.safety import untrusted_issue_block

PI_SURFACE = SurfaceSpec(
    name="pi", always_on=("AGENTS.md",), always_on_max=24000,
    always_on_cap_reason="Keep repository instructions small enough to read on every call.",
    skill_dir="skills", skill_name_rule=r"[a-z0-9][a-z0-9-]*",
    trigger_hint="Read relevant skills before editing.", autotrigger_file="AGENTS.md",
    trigger_line="Read relevant skills before editing.", subagent_requires_mode=False,
    plugin_dir=None, hooks_file=None, reject_empty_always_on=True,
)
BASE = Path(__file__).resolve().parents[2] / "harness/pi"


class PiSubstrate:
    name = "pi"

    def __init__(self, launcher):
        self.launcher = launcher

    def surface(self):
        return PI_SURFACE

    def materialise(self, tree_dir, spec, ctx):
        tree = read_tree(PI_SURFACE, tree_dir)
        directory = Path(ctx["staging_dir"])
        for name, text in tree.items():
            target = (directory / name).resolve()
            if not target.is_relative_to(directory.resolve()):
                raise ValueError("harness path escapes staging directory")
            store.write_artifact(target, text)
        digest = hashlib.sha256(json.dumps(tree, sort_keys=True).encode()).hexdigest()
        return Install(directory, digest)

    def execute(self, task_ref, install, run_ids, timeout):
        return [self.launcher(task_ref, install, run_id, timeout) for run_id in run_ids]

    def read_trajectory(self, stream_path, *, obs_trunc, max_chars, args_trunc=400):
        return ("[ACTION] pi -p\n[OBSERVATION]\n" + stream_path.read_text()[:obs_trunc])[:max_chars]

    def preflight(self):
        if not os.environ.get("LOKAY2_PROVIDER") or not os.environ.get("LOKAY2_MODEL"):
            raise RuntimeError("Set LOKAY2_PROVIDER and LOKAY2_MODEL before running lokay")


class PiProposer(Proposer):
    def _pi(self, cwd, mission, system, wall):
        store.write_artifact(cwd / "MISSION.md", (f"{system}\n\n---\n\n" if system else "") + mission)
        store.ensure_directory(cwd / "output")
        prompt = (
            "Read MISSION.md first. Do what it asks. Reply with the requested output as "
            "your final message AND save it verbatim to output/answer.md."
        )
        proc = harness_session(cwd, prompt, cwd, timeout=wall)
        if proc.returncode:
            return "", 0.0, proc.stderr or "pi failed"
        answer = cwd / "output/answer.md"
        text = answer.read_text(errors="replace") if answer.is_file() else ""
        return text if text.strip() else proc.stdout, 0.0, ""


class LokayAdapter:
    def __init__(self, repo, issue, root, start, title, body, *, findings=None, fix_round=0):
        self.task_id = f"{repo}#{issue}" + (f"@fix{fix_round}" if findings is not None else "")
        self.domain = repo.replace("/", "__")
        self.root = root
        self.start = git.git(root, "rev-parse", start)
        self.prompt = untrusted_issue_block(title, body)
        self.prompt += "\n\n" + gate_contract(git.git(root, "ls-tree", "-r", "--name-only", self.start).splitlines(), body)
        if findings is not None:
            self.prompt += "\n\nCheck findings:\n" + json.dumps(findings, ensure_ascii=False)
        self.substrate = PiSubstrate(self._launch)
        self.library = Library(HOME / "harness2/library/agg", self.domain, PI_SURFACE)
        channel = ChannelSpec("pi", f"{os.environ.get('LOKAY2_PROVIDER', '')}/{os.environ.get('LOKAY2_MODEL', '')}")
        self.spec = BenchSpec(
            name="lokay", runs_root=HOME / "harness2/runs" / self.domain,
            install_mode="workspace_agents_md", prompts=BenchPrompts(work="Implement the repository issue. Return a patch and explain the change."),
            channels={"proposer": channel, "selector": channel}, state_deliverable=True,
        )

    def tasks(self, split="all"):
        return [self.task_id]

    def domain_of(self, task_id):
        return self.domain

    def task_prompt(self, task_id):
        return self.prompt

    def task_files(self, task_id):
        return None

    def execute(self, task_id, harness_dir, run_id, *, timeout=None):
        harness_dir = harness_dir or self.base_harness()
        self.validate_tree(read_tree(PI_SURFACE, harness_dir))
        directory = self.spec.runs_root / "executions" / hashlib.sha256(run_id.encode()).hexdigest()
        if (directory / "complete.json").is_file():
            completed = json.loads((directory / "complete.json").read_text())
            if completed.get("start") != self.start:
                raise RuntimeError("completed rollout belongs to a different starting SHA")
            return directory
        install = self.substrate.materialise(harness_dir, self.spec,
                                             {"staging_dir": str(directory / "config")})
        return self.substrate.execute(task_id, install, [run_id], timeout or 3600)[0]

    def _launch(self, task_ref, install, run_id, timeout):
        directory = install.staging_dir.parent
        worktree = directory / "worktree"
        resume = False
        if (worktree.is_dir() and not worktree.is_symlink() and not (directory / "resumed").exists()
                and any(path.is_file() for path in (directory / "sessions").glob("*.jsonl"))):
            records = git.git(self.root, "worktree", "list", "--porcelain", "-z").split("\0\0")
            resume = any("detached" in record.split("\0")
                         and f"worktree {worktree.resolve()}" in record.split("\0") for record in records)
        if resume:
            store.write_artifact(directory / "resumed", "")
            store.log_event("pi_resume", directory=str(directory))
        else:
            git.detached_worktree(self.root, worktree, self.start)
        proc = harness_session(worktree, self.prompt, directory, install=install, timeout=timeout, resume=resume)
        store.write_artifact(directory / "final.md", proc.stdout or "")
        store.write_artifact(directory / "trajectory.txt", (proc.stdout or "") + "\n[ERROR]\n" + (proc.stderr or ""))
        if proc.returncode:
            raise RuntimeError(proc.stderr or "pi failed")
        store.write_artifact(directory / "patch.diff", git.worktree_patch(worktree))
        store.write_json(directory / "complete.json", {"run_id": run_id, "start": self.start})
        git.worktree_remove(self.root, worktree)
        return directory

    def delivered(self, run_dir):
        path = run_dir / "patch.diff"
        return path.is_file() and path.stat().st_size > 0

    def trajectory(self, run_dir, *, obs_trunc):
        return self.substrate.read_trajectory(run_dir / "trajectory.txt", obs_trunc=obs_trunc, max_chars=100000)

    def deliverable_files(self, run_dir):
        return {"patch.diff": self.deliverable_text(run_dir)}

    def deliverable_text(self, run_dir):
        return (run_dir / "patch.diff").read_text()

    def base_harness(self):
        entries = sorted(self.library.entries(),
                         key=lambda name: self.library.entry_dir(name).stat().st_mtime_ns,
                         reverse=True)
        for name in entries:
            directory = self.library.entry_dir(name) / "harness"
            path = directory / "AGENTS.md"
            try:
                self.validate_tree({"AGENTS.md": path.read_text() if path.is_file() else ""})
            except ValueError:
                continue
            return directory
        return BASE

    def validate_tree(self, tree):
        if not tree.get("AGENTS.md", "").strip():
            raise ValueError("Keep nonempty AGENTS.md instructions")
        lines = set(tree["AGENTS.md"].splitlines())
        for line in (BASE / "AGENTS.md").read_text().splitlines()[1:-2]:
            if line.strip() and line not in lines:
                raise ValueError(f"Keep invariant AGENTS.md rule: {line}")

    def score(self, run_dir, task_id):
        return None


def run_issue(repo, issue, root, start, title, body, *, findings=None, fix_round=0):
    start_harness_run()
    token = tick_deadline.set(None)
    try:
        adapter = LokayAdapter(repo, issue, root, start, title, body, findings=findings, fix_round=fix_round)
        store.rounds_append(repo, issue, ("Fix" if findings is not None else "Build") + " prompt:\n" + adapter.prompt)
        adapter.substrate.preflight()
        tag = hashlib.sha256((adapter.start + adapter.prompt).encode()).hexdigest()[:16]
        result = run_task(adapter.task_id, k=1,
                          adapter=cast(BenchmarkAdapter, adapter), prop=PiProposer(adapter.spec.channels["proposer"], audit_dir=adapter.spec.runs_root / "proposer"),
                          runs_root=adapter.spec.runs_root, modes=("agg",), library=adapter.library, tag=tag)
        selection = result.selections.get("agg") or {}
        chosen = selection.get("chosen_run_dir")
        empty_selection = (result.status == "partial" and selection.get("ok")
                           and (result.modes.get("agg") or {}).get("ok") and chosen
                           and result.errors == [f"agg: selected run {selection.get('chosen_run_id')} produced no deliverable"])
        if (result.status not in ("ok", "skipped") and not empty_selection) or not chosen:
            return {"result": "failed", "reason": "; ".join(result.errors) or result.status}
        directory = Path(chosen)
        complete = all((Path(row["run_dir"]) / "complete.json").is_file() for row in result.to_dict()["base"])
        executions = (adapter.spec.runs_root / "executions").resolve()
        for record in git.git(root, "worktree", "list", "--porcelain", "-z").split("\0\0"):
            fields = record.split("\0")
            if "detached" not in fields:
                continue
            for field in fields:
                if field.startswith("worktree "):
                    path = Path(field.removeprefix("worktree "))
                    if path.name == "worktree" and path.parent.parent == executions:
                        git.worktree_remove(root, path)
        return {"result": "done", "patch": directory / "patch.diff",
                "summary": (directory / "final.md").read_text(), "all_ran": complete}
    finally:
        tick_deadline.reset(token)
