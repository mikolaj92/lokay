from __future__ import annotations

import os
import stat
from pathlib import Path

from typing import Any

from lokay.config import Config, RepoConfig
from lokay.git_real_diff import (
    classify_changed_paths,
    list_changed_paths,
    list_uncommitted_paths,
)
from lokay.runner import Runner, git_spec


_QUARANTINE_SUFFIX = ".lokay-preserved"


def _is_quarantine_name(name: str) -> bool:
    return name.startswith(".") and name.endswith(_QUARANTINE_SUFFIX)


def _same_entry(left: os.stat_result, right: os.stat_result) -> bool:
    """Whether two lstat results identify the same filesystem object."""
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _pinned_entry(parent_fd: int, name: str) -> os.stat_result | None:
    """lstat *name* below the already-validated parent; never follow links."""
    try:
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError:
        return None
    return current if stat.S_ISDIR(current.st_mode) else None


def _absolute_posix_names(path: Path) -> tuple[str, ...]:
    """Absolute POSIX names with no empty, ``.``, or ``..`` components."""
    resolved = path.absolute()
    parts = resolved.parts
    if not resolved.is_absolute() or not parts or parts[0] != os.sep:
        raise ValueError("path is not absolute")
    names = parts[1:]
    if any(part in {"", ".", ".."} for part in names):
        raise ValueError("path is not lexical")
    return names


def _open_nofollow_dir(name: str, *, dir_fd: int | None = None) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    if dir_fd is None:
        return os.open(name, flags)
    return os.open(name, flags, dir_fd=dir_fd)


def _walk_nofollow(names: tuple[str, ...]) -> int:
    """Open the directory named by *names* from ``/`` without following links."""
    current_fd = _open_nofollow_dir(os.sep)
    try:
        for name in names:
            next_fd = _open_nofollow_dir(name, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


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
        if not _is_quarantine_name(child.name) and not child.is_symlink() and child.is_dir():
            found.append((child, child.name.replace("__", "/")))
    return found


def _clone_lists_worktree(runner: Runner, clone: Path, worktree: Path) -> bool | None:
    """Whether ``clone`` still owns ``worktree`` according to porcelain.

    ``None`` means the registry could not be inspected and is never evidence
    that a fallback filesystem delete is safe. NUL porcelain keeps paths
    unquoted; require complete records and at least the clone's main worktree
    rather than treating empty/truncated stdout as confirmed absence.
    """
    listed = runner.run(
        git_spec(["worktree", "list", "--porcelain", "-z"], cwd=clone, timeout_seconds=60),
        live=True,
    )
    raw = listed.stdout or ""
    if listed.returncode != 0 or (listed.stderr or "").strip() or not raw.endswith("\0\0"):
        return None
    try:
        target = worktree.resolve()
        clone_root = clone.resolve()
    except OSError:
        return None
    candidates: list[Path] = []
    for record in raw[:-2].split("\0\0"):
        fields = record.split("\0")
        if (
            not fields
            or not fields[0].startswith("worktree ")
            or not fields[0].removeprefix("worktree ")
            or not any(
                field.startswith("HEAD ")
                and len(field.removeprefix("HEAD ")) in {40, 64}
                and all(char in "0123456789abcdefABCDEF" for char in field.removeprefix("HEAD "))
                for field in fields[1:]
            )
        ):
            return None
        try:
            candidates.append(Path(fields[0].removeprefix("worktree ")).resolve())
        except OSError:
            return None
    if clone_root not in candidates:
        return None
    return target in candidates


def worktree_owned_by_clone(
    runner: Runner, clone: Path, worktree: Path
) -> bool | None:
    """Return confirmed registry ownership; ``None`` means unreadable."""
    return _clone_lists_worktree(runner, clone, worktree)


def remove_worktree(
    runner: Runner,
    clone: Path,
    worktree: Path,
    *,
    managed_root: Path,
) -> dict[str, Any]:
    """Drop a leftover worktree without deleting an unconfirmed path.

    The path must be a lexical non-symlink child of the managed root and
    registry-owned by this clone. Reinspect uncommitted content, then atomically
    archive the whole tree before pruning only Git's administrative record.
    Automated cleanup never recursively deletes archived worktree bytes.
    """
    if _is_quarantine_name(worktree.name):
        return {
            "ok": False,
            "removed": False,
            "error": "refusing preserved worktree archive path",
        }
    if worktree.is_symlink():
        return {
            "ok": False,
            "removed": False,
            "error": "refusing symlink worktree path",
        }
    archive = worktree.with_name(f".{worktree.name}{_QUARANTINE_SUFFIX}")
    try:
        root_names = _absolute_posix_names(managed_root)
        worktree_names = _absolute_posix_names(worktree)
    except ValueError:
        return {
            "ok": False,
            "removed": False,
            "error": "worktree path is outside managed root",
        }
    if worktree_names[: len(root_names)] != root_names or len(worktree_names) <= len(root_names):
        return {
            "ok": False,
            "removed": False,
            "error": "worktree path is outside managed root",
        }
    try:
        # Walk every component from the filesystem root with O_NOFOLLOW so an
        # ancestor swap above managed_root cannot redirect the archive rename.
        root_fd = _walk_nofollow(root_names)
    except OSError as exc:
        return {
            "ok": False,
            "removed": False,
            "error": f"cannot preserve worktree before registry prune: {exc}",
        }
    parent_fd = root_fd
    try:
        try:
            for component in worktree_names[len(root_names) : -1]:
                next_fd = _open_nofollow_dir(component, dir_fd=parent_fd)
                if parent_fd != root_fd:
                    os.close(parent_fd)
                parent_fd = next_fd
        except OSError:
            return {
                "ok": False,
                "removed": False,
                "error": "worktree path does not resolve lexically",
            }
        expected = _pinned_entry(parent_fd, worktree.name)
        if expected is None:
            try:
                archived = os.stat(
                    archive.name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except OSError:
                return {"ok": True, "removed": False, "already_gone": True}
            return {
                "ok": False,
                "removed": False,
                "preserved_path": str(archive),
                "error": "worktree preservation archive requires reconciliation",
            }
        # Before using pathname-based Git, ensure the lexical root and entry
        # still resolve to the exact pinned objects. Any swap fails closed.
        try:
            root_now = os.stat(managed_root, follow_symlinks=False)
            parent_now = os.stat(worktree.parent, follow_symlinks=False)
            lexical_now = worktree.lstat()
        except OSError:
            return {
                "ok": False,
                "removed": False,
                "error": "worktree path changed before preservation",
            }
        if (
            not _same_entry(root_now, os.fstat(root_fd))
            or not _same_entry(
                os.stat(managed_root, follow_symlinks=False),
                os.fstat(root_fd),
            )
            or not _same_entry(parent_now, os.fstat(parent_fd))
            or not _same_entry(lexical_now, expected)
            or not stat.S_ISDIR(lexical_now.st_mode)
        ):
            return {
                "ok": False,
                "removed": False,
                "error": "worktree path changed before preservation",
            }
        owned = _clone_lists_worktree(runner, clone, worktree)
        if owned is not True:
            return {
                "ok": False,
                "removed": False,
                "error": (
                    "cannot confirm worktree ownership before preservation"
                    if owned is None
                    else "worktree is not owned by canonical clone"
                ),
            }
        try:
            uncommitted = classify_changed_paths(
                list_uncommitted_paths(runner, worktree)
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "removed": False,
                "error": f"cannot inspect worktree before preservation: {exc}",
            }
        if uncommitted == "real":
            return {
                "ok": False,
                "removed": False,
                "error": "worktree gained uncommitted real content before preservation",
            }
        # Path-based Git queries may have raced an ancestor swap. Only the exact
        # directory inspected through the still-reachable pinned parent may move.
        current = _pinned_entry(parent_fd, worktree.name)
        try:
            parent_now = os.stat(worktree.parent, follow_symlinks=False)
            lexical_now = worktree.lstat()
        except OSError:
            return {
                "ok": False,
                "removed": False,
                "error": "worktree path changed before preservation",
            }
        if (
            current is None
            or not _same_entry(current, expected)
            or not _same_entry(parent_now, os.fstat(parent_fd))
            or not _same_entry(lexical_now, expected)
            or not stat.S_ISDIR(lexical_now.st_mode)
        ):
            return {
                "ok": False,
                "removed": False,
                "error": "worktree path changed before preservation",
            }
        archive_name = archive.name
        archive_number = 2
        while True:
            try:
                os.stat(
                    archive_name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                break
            except OSError as exc:
                return {
                    "ok": False,
                    "removed": False,
                    "error": f"cannot preserve worktree before registry prune: {exc}",
                }
            archive_name = (
                f".{worktree.name}-{archive_number}{_QUARANTINE_SUFFIX}"
            )
            archive_number += 1
        archive = worktree.with_name(archive_name)
        try:
            os.rename(
                worktree.name,
                archive.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
        except OSError as exc:
            return {
                "ok": False,
                "removed": False,
                "error": f"cannot preserve worktree before registry prune: {exc}",
            }
        try:
            archived = os.stat(
                archive.name,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            return {
                "ok": False,
                "removed": False,
                "error": f"cannot confirm preserved worktree identity: {exc}",
            }
        if not _same_entry(archived, expected) or not stat.S_ISDIR(archived.st_mode):
            return {
                "ok": False,
                "removed": False,
                "preserved_path": str(archive),
                "error": "worktree path changed during preservation",
            }
        # The pinned source is now the archive; any lexical replacement is
        # foreign and remains untouched. Automated cleanup never restores.
        try:
            original_now = os.stat(
                worktree.name,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            return {
                "ok": False,
                "removed": False,
                "preserved_path": str(archive),
                "error": "worktree path changed during preservation",
            }
        pruned = runner.run(
            git_spec(
                ["worktree", "prune", "--expire", "now"],
                cwd=clone,
                timeout_seconds=60,
            ),
            live=True,
        )
        if (
            pruned.returncode != 0
            or (pruned.stderr or "").strip()
            or (pruned.stdout or "").strip()
        ):
            detail = (pruned.stderr or pruned.stdout or "").strip()
            return {
                "ok": False,
                "removed": False,
                "preserved_path": str(archive),
                "error": detail or "git refused worktree registry prune",
            }
        still_owned = _clone_lists_worktree(runner, clone, worktree)
        if still_owned is not False:
            return {
                "ok": False,
                "removed": False,
                "preserved_path": str(archive),
                "error": (
                    "cannot confirm worktree ownership after registry prune"
                    if still_owned is None
                    else "git still owns worktree after registry prune"
                ),
            }
        return {
            "ok": True,
            "removed": True,
            "preserved_path": str(archive),
        }
    finally:
        if parent_fd != root_fd:
            os.close(parent_fd)
        os.close(root_fd)


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
        uncommitted = classify_changed_paths(
            list_uncommitted_paths(runner, worktree)
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
        "uncommitted": uncommitted,
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

    * KEEP any staged, unstaged, or untracked real implementation change
      (timeout leftover), regardless of published/behind history. Also keep an
      unpublished corner that is ahead of and contains ``origin/<base>``.
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
            try:
                uncommitted = classify_changed_paths(
                    list_uncommitted_paths(runner, worktree)
                )
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"cannot inspect uncommitted worktree changes: {exc}") from exc
            if uncommitted == "real":
                # A timeout/resume can leave new work on any branch state.
                # Published or behind-main history is not permission to erase
                # staged, unstaged, or untracked implementation changes.
                return worktree
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
            removed = remove_worktree(
                runner,
                clone,
                worktree,
                managed_root=config.worktrees_root,
            )
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
