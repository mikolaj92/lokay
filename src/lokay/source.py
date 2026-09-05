"""Load the external source plugin selected by one catalog row.

A source owns its authoritative work-item and code/change state. Lokay invokes
its task and code contracts on demand; it does not mirror the source model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from lokay.catalog import CatalogError
from lokay.code import CodeContract
from lokay.code import load_code as _load_code
from lokay.code import slot_from_repo
from lokay.models import Issue
from lokay.tasks import Task, Tasks


@dataclass(frozen=True)
class SourceContract:
    """One selected external source, exposed as work-item and code blocks."""

    plugin: str
    tasks: Tasks
    code: CodeContract


def issue_from_task(task: Task, *, repo: str) -> Issue:
    """Present a source task under the stable logical catalog identity."""
    return Issue(
        repo=repo,
        number=task.number,
        title=task.title,
        body=task.body,
        labels=list(task.labels),
        assignees=list(task.assignees),
        url=(
            f"https://github.com/{task.target}/issues/{task.number}"
            if task.plugin == "github"
            else ""
        ),
        state=task.state,
        author=task.author,
    )


def _plugin(row: Any) -> str:
    issues = getattr(row, "issues", None)
    code = getattr(row, "code", None)
    issue_plugin = str(getattr(issues, "plugin", "") or "").strip()
    code_plugin = str(getattr(code, "plugin", "") or "").strip()
    if not issue_plugin and not code_plugin and str(getattr(row, "name", "") or "").strip():
        return "github"
    if not issue_plugin or not code_plugin or issue_plugin != code_plugin:
        raise CatalogError("catalog row must use one source plugin")
    return issue_plugin


def load_tasks(
    row: Any,
    *,
    runner: object,
    config: object,
    live: bool,
    on_cap: str = "fail",
    env: Mapping[str, str] | None = None,
    client: Any = None,
    transport: Any = None,
):
    """Load the source's work-item block without copying its state."""
    plugin = _plugin(row)
    if plugin == "github":
        from lokay.github_tasks import load_tasks as load

        return load(row, runner=runner, config=config, live=live, on_cap=on_cap)
    if plugin == "azure":
        from lokay.azure_tasks import load_tasks as load

        selected = {
            "issues": {
                "plugin": plugin,
                "target": str(getattr(row.issues, "target", "")),
            }
        }
        return load(selected, env=env, client=client, transport=transport)
    raise CatalogError(f"unknown source plugin: {plugin}")


def load_code(
    row: Any,
    *,
    runner: object,
    config: object,
    live: bool,
    env: Mapping[str, str] | None = None,
    transport: Any = None,
):
    """Load the same source's repo/change block."""
    _plugin(row)
    return _load_code(
        slot_from_repo(row),
        runner=runner,
        config=config,
        live=live,
        env=env,
        transport=transport,
    )


def load_source(
    row: Any,
    *,
    runner: object,
    config: object,
    live: bool,
    on_cap: str = "fail",
    env: Mapping[str, str] | None = None,
    task_client: Any = None,
    task_transport: Any = None,
    code_transport: Any = None,
) -> SourceContract:
    """Load both blocks from one plugin without creating a source mirror."""
    plugin = _plugin(row)
    tasks = load_tasks(
        row,
        runner=runner,
        config=config,
        live=live,
        on_cap=on_cap,
        env=env,
        client=task_client,
        transport=task_transport,
    )
    code = load_code(
        row,
        runner=runner,
        config=config,
        live=live,
        env=env,
        transport=code_transport,
    )
    if tasks.plugin != plugin or code.target.plugin != plugin:
        raise CatalogError("source blocks do not belong to the selected plugin")
    return SourceContract(plugin=plugin, tasks=tasks, code=code)
