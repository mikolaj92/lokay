"""GitHub code plugin. One executor: clone/branch/worktree and PR sieve.

Calls today's gh_prs and git worktree. Same target. Zero tasks.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from lokay.code.catalog import CodeSlot
from lokay.code.contract import CodeError, CodeTarget
from lokay.code.pr import Change, ChangeChecks
from lokay.config import Config, RepoConfig
from lokay.gh_prs import (
    close_pr,
    comment_bodies,
    comment_pr,
    list_open_ai_prs,
    merge_pr,
    pr_checks_report,
    view_pr,
)
from lokay.git_worktree import InvalidBranchRef, ensure_worktree, worktree_dir
from lokay.models import PullRequest
from lokay.runner import Runner, gh_spec

__all__ = ("GithubCode", "GithubPr", "GithubRepo", "InvalidBranchRef")


def _need_name(name: str, *, what: str) -> str:
    text = str(name or "").strip()
    if not text:
        raise CodeError(f"{what} name must be non-empty")
    return text


def _repo_cfg(target: CodeTarget, clone_path: Path) -> RepoConfig:
    return RepoConfig(name=target.id, clone_path=Path(clone_path))


class GithubRepo:
    """Repo block: path, clone, branch, worktree. Today's gh clone + worktree."""

    def __init__(
        self,
        target: CodeTarget,
        *,
        clone_path: Path,
        runner: Runner,
        config: Config,
        live: bool,
    ) -> None:
        self.target = target
        self._root = Path(clone_path)
        self._runner = runner
        self._config = config
        self._live = live
        self._row = _repo_cfg(target, self._root)

    def path(self) -> Path:
        return self._root

    def clone(self) -> Path:
        if self._root.exists():
            return self._root
        if not self._live:
            return self._root
        self._root.parent.mkdir(parents=True, exist_ok=True)
        result = self._runner.run(
            gh_spec(
                ["repo", "clone", self.target.id, str(self._root)],
                timeout_seconds=600,
            ),
            live=True,
        )
        if result.returncode != 0:
            detail = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
            raise CodeError(detail or f"clone {self.target.id} failed")
        return self._root

    def branch(self, name: str) -> str:
        head = _need_name(name, what="branch")
        self.clone()
        return head

    def worktree(self, name: str, *, base: str = "main", reset_to_base: bool = False) -> Path:
        head = _need_name(name, what="worktree")
        if not self._live:
            return worktree_dir(self._config, self._row, head)
        return ensure_worktree(
            self._runner,
            self._config,
            self._row,
            head,
            live=True,
            base=base,
            reset_to_base=reset_to_base,
        )


class GithubPr:
    """PR sieve: list, get, checks, comment, merge-commit, close. No tasks."""

    def __init__(
        self,
        target: CodeTarget,
        *,
        runner: Runner,
        config: Config,
        live: bool,
        repo_row: RepoConfig,
    ) -> None:
        self.target = target
        self._runner = runner
        self._config = config
        self._live = live
        self._row = repo_row
        self._listed: dict[int, PullRequest] = {}
        self._last_checks: dict[str, Any] = {}

    def _to_change(self, row: PullRequest, *, state: str = "open") -> Change:
        return Change(
            target=self.target,
            number=int(row.number),
            title=str(row.title or ""),
            body=str(row.body or ""),
            head=str(row.head_ref or ""),
            state=state,
        )

    def _from_view(self, view: dict[str, Any], number: int) -> Change:
        comments = tuple(comment_bodies(view))
        status = "none"
        rollup = view.get("statusCheckRollup")
        if isinstance(rollup, list) and rollup:
            status = "pending"
        return Change(
            target=self.target,
            number=int(view.get("number") or number),
            title=str(view.get("title") or ""),
            body=str(view.get("body") or ""),
            head=str(view.get("headRefName") or ""),
            state="open",
            comments=comments,
            checks_status=status,
        )

    def lokay_dicts(self) -> list[dict[str, Any]]:
        """Today's list_prs envelope rows (PullRequest.to_dict)."""
        return [row.to_dict() for row in self._listed.values()]

    @property
    def last_checks_report(self) -> dict[str, Any]:
        return dict(self._last_checks)

    def list_open(self) -> list[Change]:
        rows = list_open_ai_prs(self._runner, self._config, self._row, live=self._live)
        self._listed = {int(row.number): row for row in rows}
        return [self._to_change(row) for row in rows]

    def get(self, number: int) -> Change:
        view = view_pr(self._runner, self.target.id, int(number), live=self._live)
        if view:
            return self._from_view(view, int(number))
        row = self._listed.get(int(number))
        if row is not None:
            return self._to_change(row)
        raise CodeError(f"change {number} not on {self.target}")

    def checks(self, number: int) -> ChangeChecks:
        report = pr_checks_report(
            self._runner, self.target.id, int(number), live=self._live
        )
        self._last_checks = dict(report)
        status = str(report.get("status") or "failed")
        return ChangeChecks(status=status, green=bool(report.get("green")))

    def comment(self, number: int, body: str) -> Change:
        text = str(body or "").strip()
        if not text:
            raise CodeError("comment body must be non-empty")
        comment_pr(self._runner, self.target.id, int(number), text, live=self._live)
        try:
            row = self.get(int(number))
        except CodeError:
            row = Change(
                target=self.target,
                number=int(number),
                title="",
                body="",
                head="",
                state="open",
                comments=(text,),
            )
        if text not in row.comments:
            return replace(row, comments=row.comments + (text,))
        return row

    def merge_commit(self, number: int) -> Change:
        merge_pr(self._runner, self.target.id, int(number), live=self._live)
        try:
            row = self.get(int(number))
        except CodeError:
            row = Change(
                target=self.target,
                number=int(number),
                title="",
                body="",
                head="",
                state="open",
            )
        if not self._live:
            return replace(row, merge_method="merge")
        return replace(row, state="merged", merge_method="merge")

    def close(self, number: int, comment: str = "") -> Change:
        close_pr(
            self._runner,
            self.target.id,
            int(number),
            live=self._live,
            comment=str(comment or ""),
        )
        try:
            row = self.get(int(number))
        except CodeError:
            row = Change(
                target=self.target,
                number=int(number),
                title="",
                body="",
                head="",
                state="open",
            )
        if not self._live:
            return row
        return replace(row, state="closed")


class GithubCode:
    """One GitHub host. Repo and PR share this target. No task list."""

    def __init__(
        self,
        target: CodeTarget,
        *,
        clone_path: Path,
        runner: Runner,
        config: Config,
        live: bool,
    ) -> None:
        if target.plugin != "github":
            raise CodeError(f"github plugin cannot bind {target}")
        self.target = target
        row = _repo_cfg(target, clone_path)
        self.repo = GithubRepo(
            target,
            clone_path=clone_path,
            runner=runner,
            config=config,
            live=live,
        )
        self.pr = GithubPr(
            target,
            runner=runner,
            config=config,
            live=live,
            repo_row=row,
        )

    @classmethod
    def from_slot(
        cls,
        slot: CodeSlot,
        *,
        runner: Runner,
        config: Config,
        live: bool,
    ) -> GithubCode:
        if slot.plugin != "github":
            raise CodeError(f"unknown code plugin: {slot.plugin}")
        return cls(
            CodeTarget(plugin="github", id=slot.target),
            clone_path=slot.clone_path,
            runner=runner,
            config=config,
            live=live,
        )
