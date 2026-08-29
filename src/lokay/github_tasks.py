"""GitHub tasks plugin. Issue = task. Parent calls the contract.

Calls existing gh_issues. Zero PR, clone, git, merge, close.
Assignees are GitHub logins. Sito foreign-assignee lives in #881, not here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lokay.config import Config, RepoConfig
from lokay.gh_issues import (
    add_issue_labels,
    comment_issue,
    get_issue as view_issue,
    list_issues_with_label,
    list_ready_issues,
    remove_issue_labels,
)
from lokay.models import Issue
from lokay.tasks import Task, TaskId, _require_mark

PLUGIN = "github"


def issues_slot(row: Any) -> tuple[str, str]:
    """Read issues.plugin / issues.target. Ignore code and prs."""
    if not isinstance(row, dict):
        issues = getattr(row, "issues", None)
        name = str(getattr(row, "name", "") or "").strip()
        if issues is None:
            if not name:
                raise ValueError("catalog row needs issues.plugin and issues.target")
            return PLUGIN, name
        if isinstance(issues, dict):
            plugin = str(issues.get("plugin") or PLUGIN).strip()
            target = str(issues.get("target") or name).strip()
        else:
            plugin = str(getattr(issues, "plugin", None) or PLUGIN).strip()
            target = str(getattr(issues, "target", None) or name).strip()
        if not plugin or not target:
            raise ValueError("catalog row needs issues.plugin and issues.target")
        return plugin, target
    issues = row.get("issues")
    if not isinstance(issues, dict):
        raise ValueError("catalog row needs issues.plugin and issues.target")
    plugin = str(issues.get("plugin") or "").strip()
    target = str(issues.get("target") or "").strip()
    if not plugin or not target:
        raise ValueError("catalog row needs issues.plugin and issues.target")
    return plugin, target


def catalog_row(config: object, repo_name: str) -> RepoConfig:
    """Catalog row for a target, or a github default when the name is absent."""
    for row in getattr(config, "repos", None) or []:
        if getattr(row, "name", None) == repo_name:
            return row
    root = getattr(config, "worktrees_root", None)
    clone = Path(root) / "unused" if root else Path(".")
    return RepoConfig(name=repo_name, clone_path=clone)


def load_tasks(
    row: Any,
    *,
    runner: object,
    config: Config,
    live: bool,
    on_cap: str = "fail",
) -> GitHubTasks:
    """Catalog `issues.plugin: github` loads this plugin. Does not read code/prs."""
    plugin, target = issues_slot(row)
    if plugin != PLUGIN:
        raise ValueError(f"issues.plugin {plugin!r} is not github")
    return GitHubTasks(
        row=row,
        target=target,
        runner=runner,
        config=config,
        live=live,
        on_cap=on_cap,
    )


def issue_to_task(issue: object, *, plugin: str, target: str) -> Task:
    """Map a GitHub issue row onto the contract. Assignee logins -> assignees."""
    labels = list(getattr(issue, "labels", None) or [])
    return Task(
        plugin=plugin,
        target=target or str(getattr(issue, "repo", "") or ""),
        number=int(issue.number),
        title=str(getattr(issue, "title", "") or ""),
        body=str(getattr(issue, "body", "") or ""),
        labels=labels,
        assignees=list(getattr(issue, "assignees", None) or []),
        state=str(getattr(issue, "state", "") or "OPEN").upper(),
        author=str(getattr(issue, "author", "") or ""),
        mark=_mark_from_labels(labels),
        comments=list(getattr(issue, "comments", None) or []),
    )


def task_to_issue(task: Task) -> Issue:
    return Issue(
        repo=task.target,
        number=task.number,
        title=task.title,
        body=task.body,
        labels=list(task.labels),
        assignees=list(task.assignees),
        url=f"https://github.com/{task.target}/issues/{task.number}",
        state=task.state,
        author=task.author,
    )


def _mark_from_labels(labels: list[str]) -> str | None:
    have = set(labels)
    if "ai:ready" in have:
        return "ready"
    if "ai:park" in have:
        return "park"
    if "ai:blocked" in have:
        return "blocked"
    if "work:ready" in have:
        return "ready"
    return None


class GitHubTasks:
    """Tasks executor for GitHub issues. Zero PR, clone, git, merge."""

    def __init__(
        self,
        *,
        row: object,
        target: str,
        runner: object,
        config: Config,
        live: bool,
        on_cap: str = "fail",
    ) -> None:
        identity = TaskId(PLUGIN, target, 1)
        self.plugin = identity.plugin
        self.target = identity.target
        self._row = row
        self._runner = runner
        self._config = config
        self._live = live
        self._on_cap = on_cap

    def _same(self, identity: TaskId) -> bool:
        return identity.plugin == self.plugin and identity.target == self.target

    def _list_repo(self) -> object:
        if getattr(self._row, "name", None) == self.target:
            return self._row
        clone = getattr(self._row, "clone_path", Path("."))
        return RepoConfig(name=self.target, clone_path=Path(clone))

    def _to_task(self, issue: object) -> Task:
        return issue_to_task(issue, plugin=self.plugin, target=self.target)

    def list_open(self) -> list[Task]:
        kwargs: dict = {"live": self._live}
        if self._on_cap != "fail":
            kwargs["on_cap"] = self._on_cap
        rows = list_ready_issues(self._runner, self._config, self._list_repo(), **kwargs)
        return [self._to_task(row) for row in rows]

    def list_labeled(self, label: str) -> list[Task]:
        rows = list_issues_with_label(
            self._runner, self._config, self._list_repo(), label=label, live=self._live
        )
        return [self._to_task(row) for row in rows]

    def get(self, identity: TaskId) -> Task | None:
        if not self._same(identity):
            return None
        issue = view_issue(
            self._runner, self._config, self.target, identity.number, live=self._live
        )
        if issue is None:
            return None
        return self._to_task(issue)

    def comment(self, identity: TaskId, body: str) -> Task:
        if not self._same(identity):
            raise KeyError(
                f"task not found: {identity.plugin}+{identity.target}+{identity.number}"
            )
        text = str(body or "")
        if not text.strip():
            raise ValueError("comment body must be non-empty")
        current = self.get(identity)
        if current is None:
            raise KeyError(
                f"task not found: {identity.plugin}+{identity.target}+{identity.number}"
            )
        comment_issue(self._runner, self.target, identity.number, text, live=self._live)
        current.comments.append(text)
        return current

    def mark(self, identity: TaskId, kind: str) -> Task:
        if not self._same(identity):
            raise KeyError(
                f"task not found: {identity.plugin}+{identity.target}+{identity.number}"
            )
        token = _require_mark(kind)
        current = self.get(identity)
        if current is None:
            raise KeyError(
                f"task not found: {identity.plugin}+{identity.target}+{identity.number}"
            )
        ready = str(getattr(self._config, "ready_label", None) or "ai:ready")
        blocked = str(getattr(self._config, "blocked_label", None) or "ai:blocked")
        drop = {ready, "work:ready", blocked, "ai:park"}
        have = set(current.labels)
        remove = [label for label in current.labels if label in drop]
        if remove:
            remove_issue_labels(
                self._runner, self.target, identity.number, remove, live=self._live
            )
        add: list[str] = []
        if token == "ready":
            add.append(ready)
        else:
            add.append(blocked)
        add = [label for label in add if label not in (have - set(remove))]
        if add:
            add_issue_labels(
                self._runner, self.target, identity.number, add, live=self._live
            )
        out = self.get(identity) or current
        # Park / ready / blocked stay open. This plugin has no close.
        out.mark = token
        out.state = "OPEN"
        labels = [label for label in out.labels if label not in drop]
        if token == "ready":
            labels.append(ready)
        else:
            labels.append(blocked)
        out.labels = labels
        return out

issues_source = load_tasks
