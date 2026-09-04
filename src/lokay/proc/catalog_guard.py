"""Atomic: copy aside skip-worktree repos.mikolaj92.yaml around lokay git pull/ff.

Before fast-forward of the lokay checkout, ``--save`` copies the catalog if it is
skip-worktree (or ``--assume-skip-worktree``). After pull/ff, ``--restore``
writes the copy back. Fail-closed when restore cannot write.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from lokay.envelope import emit_exit, err, ok

CATALOG_REL = "repos.mikolaj92.yaml"
ASIDE_DIR = "lokay-catalog-guard"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        stdin=subprocess.DEVNULL,
    )


def _git_dir(repo_root: Path) -> Path | None:
    done = _git(repo_root, "rev-parse", "--git-dir")
    if done.returncode != 0:
        return None
    raw = Path((done.stdout or "").strip())
    if not raw.is_absolute():
        raw = (repo_root / raw).resolve()
    return raw if raw.exists() else None


def _aside_path(repo_root: Path) -> Path:
    git_dir = _git_dir(repo_root)
    if git_dir is not None:
        return git_dir / ASIDE_DIR / CATALOG_REL
    return repo_root / ".lokay-catalog-guard" / CATALOG_REL


def _is_skip_worktree(repo_root: Path, rel: str) -> bool:
    done = _git(repo_root, "ls-files", "-v", "--", rel)
    if done.returncode != 0:
        raise RuntimeError((done.stderr or done.stdout or "git ls-files failed").strip())
    line = (done.stdout or "").strip()
    return bool(line) and line[0] in {"S", "s"}


def _save(*, repo_root: Path, assume: bool) -> dict:
    catalog = repo_root / CATALOG_REL
    path = str(catalog)
    try:
        skip = assume or _is_skip_worktree(repo_root, CATALOG_REL)
    except Exception as exc:  # noqa: BLE001
        return err(str(exc), protected=False, path=path)
    if not skip:
        return ok(protected=False, path=path)
    if not catalog.is_file():
        return err("catalog missing; cannot copy aside", protected=True, path=path)
    aside = _aside_path(repo_root)
    try:
        aside.parent.mkdir(parents=True, exist_ok=True)
        aside.write_bytes(catalog.read_bytes())
    except OSError as exc:
        return err(f"catalog save cannot copy aside: {exc}", protected=True, path=path)
    return ok(protected=True, path=path)


def _restore(*, repo_root: Path) -> dict:
    catalog = repo_root / CATALOG_REL
    path = str(catalog)
    aside = _aside_path(repo_root)
    if not aside.is_file():
        return ok(protected=False, path=path)
    try:
        data = aside.read_bytes()
        catalog.write_bytes(data)
    except OSError as exc:
        return err(f"catalog restore cannot write: {exc}", protected=True, path=path)
    aside.unlink(missing_ok=True)
    return ok(protected=True, path=path)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-catalog-guard")
    p.add_argument("--repo-root", required=True, help="lokay checkout root")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--save", action="store_true", help="copy catalog aside before pull/ff")
    mode.add_argument("--restore", action="store_true", help="restore catalog after pull/ff")
    p.add_argument(
        "--assume-skip-worktree",
        action="store_true",
        help="treat repos.mikolaj92.yaml as skip-worktree even if git does not report it",
    )
    args = p.parse_args(argv)
    root = Path(args.repo_root).expanduser().resolve()
    if not root.is_dir():
        return emit_exit(err("repo-root is not a directory", path=str(root), protected=False))
    if args.save:
        return emit_exit(_save(repo_root=root, assume=bool(args.assume_skip_worktree)))
    return emit_exit(_restore(repo_root=root))


if __name__ == "__main__":
    raise SystemExit(main())
