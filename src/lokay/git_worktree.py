from __future__ import annotations

from pathlib import Path

from typing import Any

from lokay.config import Config, RepoConfig
from lokay.git_real_diff import classify_changed_paths, list_changed_paths
from lokay.runner import Runner, git_spec


class InvalidBranchRef(ValueError):
    """Git will not accept this as ``refs/heads/*`` (e.g. a ``..`` slug)."""

    def __init__(self, branch: str, detail: str = "") -> None:
        self.branch = branch
        self.reason = "invalid_branch_ref"
        msg = f"invalid branch ref: {branch}"
        if detail:
            msg = f"{msg}: {detail}"
        super().__init__(msg)


def assert_valid_branch_ref(
    runner: Runner,
    branch: str,
    *,
    cwd: Path | None = None,
) -> None:
    """Fail closed before ``git worktree add`` if the head is not a legal ref."""
    result = runner.run(
        git_spec(
            ["check-ref-format", "--normalize", f"refs/heads/{branch}"],
            cwd=cwd,
            timeout_seconds=30,
        ),
        live=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise InvalidBranchRef(branch, detail)


def _missing_remote_ref(detail: str) -> bool:
    low = detail.lower()
    return "couldn't find remote ref" in low or "could not find remote ref" in low


def _rev_count(runner: Runner, worktree: Path, spec: str) -> int | None:
    result = runner.run(
        git_spec(["rev-list", "--count", spec], cwd=worktree, timeout_seconds=60),
        live=True,
    )
    if result.returncode != 0:
        return None
    try:
        return int((result.stdout or "").strip() or "0")
    except ValueError:
        return None


def _behind_own_remote(
    runner: Runner, worktree: Path, clone: Path, branch: str
) -> int | None:
    """Commits on ``origin/<branch>`` that HEAD lacks. ``None`` if unpublished."""
    fetched = runner.run(
        git_spec(["fetch", "origin", branch], cwd=clone, timeout_seconds=180),
        live=True,
    )
    if fetched.returncode != 0:
        detail = (fetched.stderr or fetched.stdout or "").strip()
        if _missing_remote_ref(detail):
            return None
        raise RuntimeError(f"cannot determine origin/{branch}: {detail}")
    result = runner.run(
        git_spec(
            ["rev-list", "--count", f"HEAD..origin/{branch}"],
            cwd=worktree,
            timeout_seconds=60,
        ),
        live=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"cannot measure behind vs origin/{branch}: {detail}")
    try:
        return int((result.stdout or "").strip() or "0")
    except ValueError as exc:
        raise RuntimeError(
            f"cannot measure behind vs origin/{branch}: "
            f"{(result.stdout or '').strip()!r}"
        ) from exc


def worktree_dir(config: Config, repo: RepoConfig, branch: str) -> Path:
    return config.worktrees_root / repo.name.replace("/", "__") / branch.replace("/", "__")


def iter_worktrees(config: Config, repo: RepoConfig) -> list[tuple[Path, str]]:
    """Existing leftover corners for *repo*: ``(path, branch)``."""
    root = config.worktrees_root / repo.name.replace("/", "__")
    if not root.is_dir():
        return []
    found: list[tuple[Path, str]] = []
    for child in sorted(root.iterdir()):
        if child.is_dir():
            found.append((child, child.name.replace("__", "/")))
    return found


def remove_worktree(runner: Runner, clone: Path, worktree: Path) -> dict[str, Any]:
    """Drop a leftover worktree. Never ``rm -rf`` a path git still owns."""
    if not worktree.exists():
        return {"ok": True, "removed": False, "already_gone": True}
    rm = runner.run(
        git_spec(
            ["worktree", "remove", "--force", str(worktree)],
            cwd=clone,
            timeout_seconds=120,
        ),
        live=True,
    )
    if worktree.exists():
        # Detached/corrupt registry, or a test runner that does not delete.
        import shutil

        shutil.rmtree(worktree, ignore_errors=True)
        runner.run(
            git_spec(["worktree", "prune"], cwd=clone, timeout_seconds=60),
            live=True,
        )
    if worktree.exists():
        detail = (rm.stderr or rm.stdout or "").strip()
        return {
            "ok": False,
            "removed": False,
            "error": detail or "worktree still exists after remove",
        }
    return {"ok": True, "removed": True}


def remote_heads(runner: Runner, clone: Path) -> set[str] | None:
    """Branch names on ``origin``. ``None`` is fail-closed, not unpublished."""
    listed = runner.run(
        git_spec(["ls-remote", "--heads", "origin"], cwd=clone, timeout_seconds=180),
        live=True,
    )
    if listed.returncode != 0:
        return None
    heads: set[str] = set()
    for line in (listed.stdout or "").splitlines():
        _, sep, ref = line.partition("refs/heads/")
        if sep:
            name = ref.strip()
            if name:
                heads.add(name)
    return heads


def leftover_status(
    runner: Runner,
    worktree: Path,
    clone: Path,
    branch: str,
    *,
    base: str = "main",
    fetch_base: bool = True,
    known_published: bool | None = None,
) -> dict[str, Any]:
    """Classify a leftover corner. ``readable=False`` is fail-closed (KEEP).

    * ``keep_unpublished`` — never pushed, and either already contains
      ``origin/<base>`` or has a dirty real tree (timeout resume).
    * ``published`` — ``origin/<branch>`` exists (including a closed
      CONFLICTING tip). Replaying that tip is a dirty-PR loop; reap it.
    * Fetch / rev-list flake is not unpublished.
    * ``known_published`` skips the per-branch fetch when the atom already
      listed ``origin`` heads once.
    """
    if not worktree.is_dir():
        return {"readable": False, "error": "worktree missing"}
    if fetch_base:
        fetched = runner.run(
            git_spec(["fetch", "origin", base], cwd=clone, timeout_seconds=300),
            live=True,
        )
        if fetched.returncode != 0:
            detail = (fetched.stderr or fetched.stdout or "").strip()
            return {
                "readable": False,
                "error": f"cannot fetch origin/{base}: {detail}",
            }
    ahead_result = runner.run(
        git_spec(
            ["rev-list", "--count", f"origin/{base}..HEAD"],
            cwd=worktree,
            timeout_seconds=60,
        ),
        live=True,
    )
    if ahead_result.returncode != 0:
        detail = (ahead_result.stderr or ahead_result.stdout or "").strip()
        return {"readable": False, "error": f"cannot measure ahead: {detail}"}
    try:
        ahead = int((ahead_result.stdout or "").strip() or "0")
    except ValueError:
        return {
            "readable": False,
            "error": f"cannot parse ahead: {(ahead_result.stdout or '').strip()!r}",
        }
    behind_main = _rev_count(runner, worktree, f"HEAD..origin/{base}")
    if behind_main is None:
        return {
            "readable": False,
            "error": f"cannot measure behind vs origin/{base}",
        }
    if known_published is None:
        try:
            behind_own = _behind_own_remote(runner, worktree, clone, branch)
        except RuntimeError as exc:
            return {"readable": False, "error": str(exc)}
        published = behind_own is not None
    else:
        published = bool(known_published)
    try:
        dirty = classify_changed_paths(
            list_changed_paths(runner, worktree, base=f"origin/{base}")
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "readable": False,
            "error": f"cannot classify leftover tree vs origin/{base}: {exc}",
        }
    keep_unpublished = (not published) and (
        (ahead > 0 and behind_main == 0) or dirty == "real"
    )
    return {
        "readable": True,
        "ahead": ahead,
        "behind_main": behind_main,
        "published": published,
        "dirty": dirty,
        "keep_unpublished": keep_unpublished,
    }


def ensure_worktree(
    runner: Runner,
    config: Config,
    repo: RepoConfig,
    branch: str,
    *,
    live: bool,
    base: str = "main",
    reset_to_base: bool = False,
) -> Path:
    """Ensure a worktree for *branch*.

    When ``reset_to_base`` is True (issue_to_pr re-implement path):

    * KEEP if the existing corner is unpublished (no ``origin/<branch>``),
      ahead of ``origin/<base>``, and already contains ``origin/<base>``,
      **or** has a dirty real tree (timeout leftover). Restart must not
      wipe a child that has not published a PR and can still push.
    * RESET (``-B`` from ``origin/<base>`` + best-effort remote delete) when
      ``origin/<branch>`` exists — including a closed CONFLICTING tip that
      matches HEAD. Replaying those commits just republishes the same dirty
      PR. Also reset when ahead is 0 and the tree is clean, or when ahead of
      base and behind ``origin/<branch>`` (NFF reuse). Never force-push.
    * Fail closed if ahead cannot be measured. Do not ``rm -rf``.
    """
    worktree = worktree_dir(config, repo, branch)
    if not live:
        return worktree

    clone = repo.clone_path
    assert_valid_branch_ref(runner, branch, cwd=clone if Path(clone).exists() else None)

    worktree.parent.mkdir(parents=True, exist_ok=True)
    runner.run_checked(
        git_spec(["fetch", "origin", base], cwd=clone, timeout_seconds=300),
        live=True,
    )
    start_ref = f"origin/{base}"

    if reset_to_base:
        if worktree.exists():
            ahead_result = runner.run(
                git_spec(
                    ["rev-list", "--count", f"origin/{base}..HEAD"],
                    cwd=worktree,
                    timeout_seconds=60,
                ),
                live=True,
            )
            if ahead_result.returncode != 0:
                detail = (ahead_result.stderr or ahead_result.stdout or "").strip()
                raise RuntimeError(
                    f"cannot measure unpublished ahead vs origin/{base}: {detail}"
                )
            try:
                ahead = int((ahead_result.stdout or "").strip())
            except ValueError as exc:
                raise RuntimeError(
                    f"cannot measure unpublished ahead vs origin/{base}: "
                    f"{(ahead_result.stdout or '').strip()!r}"
                ) from exc
            if ahead > 0:
                behind = _behind_own_remote(runner, worktree, clone, branch)
                if behind is None:
                    # Never pushed. KEEP only when the leftover is already
                    # on current origin/<base>. Stale unpublished commits
                    # (behind main) are a rebase_conflict loop waiting to
                    # happen — RESET and re-implement.
                    behind_main = _rev_count(
                        runner, worktree, f"HEAD..origin/{base}"
                    )
                    if behind_main is None:
                        raise RuntimeError(
                            f"cannot measure behind vs origin/{base}"
                        )
                    if behind_main == 0:
                        return worktree
                # origin/<branch> exists, or unpublished-but-stale vs main.
                # Fall through and recreate from origin/<base>.
            else:
                try:
                    dirty = classify_changed_paths(
                        list_changed_paths(runner, worktree, base=f"origin/{base}")
                    )
                except Exception as exc:  # noqa: BLE001
                    raise RuntimeError(
                        f"cannot classify leftover tree vs origin/{base}: {exc}"
                    ) from exc
                if dirty == "real":
                    # Timeout leftover: agent wrote files but did not commit.
                    # Next pass must resume this corner, not wipe it.
                    return worktree
            removed = remove_worktree(runner, clone, worktree)
            if not removed.get("ok"):
                raise RuntimeError(
                    f"worktree remove failed: {removed.get('error') or 'still exists'}"
                )
        # -B: create or reset branch to start_ref at the new worktree path.
        result = runner.run(
            git_spec(
                ["worktree", "add", "-B", branch, str(worktree), start_ref],
                cwd=clone,
                timeout_seconds=180,
            ),
            live=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"worktree reset-to-base failed:\n{result.stderr}\n{result.stdout}"
            )
        # Drop stale remote tip (old conflicting commits) so push need not force.
        runner.run(
            git_spec(
                ["push", "origin", "--delete", branch],
                cwd=clone,
                timeout_seconds=120,
            ),
            live=True,
        )
        return worktree

    if worktree.exists():
        return worktree

    result = runner.run(
        git_spec(
            ["worktree", "add", "-b", branch, str(worktree), start_ref],
            cwd=clone,
            timeout_seconds=180,
        ),
        live=True,
    )
    if result.returncode != 0:
        result2 = runner.run(
            git_spec(["worktree", "add", str(worktree), branch], cwd=clone, timeout_seconds=180),
            live=True,
        )
        if result2.returncode != 0:
            result3 = runner.run(
                git_spec(
                    [
                        "worktree",
                        "add",
                        "--track",
                        "-b",
                        branch,
                        str(worktree),
                        f"origin/{branch}",
                    ],
                    cwd=clone,
                    timeout_seconds=180,
                ),
                live=True,
            )
            if result3.returncode != 0:
                raise RuntimeError(
                    "worktree add failed:\n"
                    f"{result.stderr}\n{result2.stderr}\n{result3.stderr}"
                )
    return worktree
