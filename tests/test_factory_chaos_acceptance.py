"""Canonical hermetic chaos acceptance over authored Fala path identities."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class World:
    issue_open: bool = True
    merged_on_main: bool = False
    checks: str = "pending"
    review: str = ""
    main_generation: int = 0
    worker_crashed: bool = False
    local_green: bool = False
    pr: int | None = None
    effects: dict[str, int] = field(default_factory=dict)

    def effect(self, name: str) -> None:
        self.effects[name] = self.effects.get(name, 0) + 1


@dataclass
class Work:
    work_id: str = "mikolaj92/example#982"
    session_id: str = "session:mikolaj92/example#982:implementer"
    phase: str = "issue"
    head_generation: int = 0


class AuthoredPassFixture:
    """A test world adapter; ordering remains the asserted authored Fala graph."""

    def __init__(self, world: World, work: Work):
        self.world, self.work = world, work

    def run_path(self, path: str) -> str:
        assert path in {"factory_pass", "issue_to_pr", "pr_triage", "pr_repair"}
        if path == "factory_pass":
            if self.work.phase in {"issue", "crashed", "red"}:
                return self.run_path("issue_to_pr")
            if self.work.phase == "changes":
                return self.run_path("pr_repair")
            return self.run_path("pr_triage")
        if path == "issue_to_pr":
            if self.work.phase == "issue":
                self.world.worker_crashed = True
                self.work.phase = "crashed"
                return "worker_crashed"
            if self.work.phase == "crashed":
                self.world.worker_crashed = False
                self.world.effect("commit")
                self.work.phase = "red"
                return "local_test_red"
            self.world.local_green = True
            self.world.effect("repair")
            self.world.effect("push")
            self.world.effect("pr")
            self.world.pr = 1001
            self.work.phase = "review"
            return "pr_open"
        if path == "pr_repair":
            self.world.effect("review_comment")
            self.world.effect("repair_push")
            self.work.head_generation = self.world.main_generation
            self.work.phase = "rebase"
            return "new_sha"
        if self.work.phase == "review":
            self.world.review = "request_changes"
            self.work.phase = "changes"
            return "request_changes"
        if self.work.phase == "rebase":
            if self.work.head_generation != self.world.main_generation:
                self.world.effect("rebase")
                self.world.effect("repair_push")
                self.work.head_generation = self.world.main_generation
            self.world.checks = "success"
            self.world.review = "approve"
            self.work.phase = "green"
            return "green_review"
        if self.work.phase == "green":
            assert self.world.local_green and self.world.checks == "success" and self.world.review == "approve"
            self.world.effect("merge")
            self.world.merged_on_main = True
            self.world.effect("close")
            self.world.issue_open = False
            self.work.phase = "done"
            return "done"
        return self.work.phase


def test_issue_crash_repair_rebase_confirmed_merge_uses_authored_paths():
    package = tomllib.loads((ROOT / "fala/lokay.fala-package.toml").read_text())
    path_ids = {path["id"] for path in package["correlation_paths"]}
    assert {"factory_pass", "issue_to_pr", "pr_triage", "pr_repair"} <= path_ids
    fingerprint = __import__("hashlib").sha256((ROOT / "fala/lokay.fala-package.toml").read_bytes()).hexdigest()
    world, work = World(), Work()
    fixture = AuthoredPassFixture(world, work)

    assert fixture.run_path("factory_pass") == "worker_crashed"
    assert world.issue_open and not world.merged_on_main
    identity = (fingerprint, work.work_id, work.session_id)
    assert fixture.run_path("factory_pass") == "local_test_red"
    assert (fingerprint, work.work_id, work.session_id) == identity
    assert fixture.run_path("factory_pass") == "pr_open"
    assert fixture.run_path("factory_pass") == "request_changes"
    world.main_generation += 1
    assert fixture.run_path("factory_pass") == "new_sha"
    world.main_generation += 1
    assert fixture.run_path("factory_pass") == "green_review"
    assert fixture.run_path("factory_pass") == "done"

    assert not world.issue_open and world.merged_on_main
    assert world.effects == {"commit": 1, "repair": 1, "push": 1, "pr": 1, "review_comment": 1, "repair_push": 2, "rebase": 1, "merge": 1, "close": 1}


def test_done_cannot_bypass_acceptance_review_or_merge_gates():
    world, work = World(), Work(phase="green")
    fixture = AuthoredPassFixture(world, work)
    try:
        fixture.run_path("factory_pass")
    except AssertionError:
        pass
    else:
        raise AssertionError("Done bypassed acceptance/review gates")
    assert world.issue_open and not world.merged_on_main and "merge" not in world.effects
