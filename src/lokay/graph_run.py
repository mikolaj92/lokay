"""Run a Fala correlation path from lokay's package (order is the product)."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any

def _project_root() -> Path:
    """Resolve checkout root (editable src layout or CWD)."""
    here = Path(__file__).resolve()
    # src/lokay/graph_run.py → parents[2] == repo root
    src_layout = here.parents[2]
    if (src_layout / "fala" / "lokay.fala-package.toml").is_file():
        return src_layout
    cwd = Path.cwd()
    if (cwd / "fala" / "lokay.fala-package.toml").is_file():
        return cwd
    # packaged data next to this module
    data = here.parent / "data" / "lokay.fala-package.toml"
    if data.is_file():
        return here.parent  # not really project root; find_package handles
    return cwd


def find_default_package() -> Path:
    env = os.environ.get("LOKAY_FALA_PACKAGE")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "fala" / "lokay.fala-package.toml",  # src/lokay → repo
        Path.cwd() / "fala" / "lokay.fala-package.toml",
        here.parent / "data" / "lokay.fala-package.toml",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "fala/lokay.fala-package.toml not found; set LOKAY_FALA_PACKAGE or run from repo root"
    )


ROOT = _project_root()


def _python() -> str:
    return sys.executable


def _materialize_package(src: Path, dest: Path) -> Path:
    """Write package with absolute Python for subprocess adapters."""
    text = src.read_text(encoding="utf-8")
    text = text.replace("PLACEHOLDER_PYTHON", _python())
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return dest


def run_path(
    *,
    path_id: str,
    repo: str,
    issue: int | None = None,
    config_path: str | Path | None = None,
    live: bool = False,
    package_path: str | Path | None = None,
    db_path: str | Path | None = None,
    run_id: str | None = None,
    max_ticks: int = 64,
) -> dict[str, Any]:
    """Drive Fala host_run_package for a Lokay graph path."""
    try:
        from fala import host_run_package
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "fala package is required: uv add / path to Fala python binding"
        ) from exc

    pkg_src = Path(package_path) if package_path else find_default_package()
    if not pkg_src.is_file():
        raise FileNotFoundError(f"Fala package not found: {pkg_src}")

    work = Path(db_path) if db_path else Path.home() / ".lokay" / "fala"
    work.mkdir(parents=True, exist_ok=True)
    pkg_runtime = work / "lokay.fala-package.toml"
    _materialize_package(pkg_src, pkg_runtime)
    db = work / "state.sqlite"

    cfg = str(Path(config_path).expanduser().resolve()) if config_path else ""
    base_input: dict[str, Any] = {
        "repo": repo,
        "live": bool(live),
    }
    if cfg:
        base_input["config_path"] = cfg
        os.environ.setdefault("LOKAY_CONFIG", cfg)
    if issue is not None:
        base_input["issue"] = int(issue)
        base_input["issue_number"] = int(issue)

    # Same authored inputs for every step; atoms pick what they need.
    steps = [
        "get_issue",
        "assign_issue",
        "make_branch",
        "worktree_add",
        "run_agent",
        "commit_all",
        "push",
        "pr_create",
        "list_prs",
        "pr_label",
    ]
    effector_inputs = {step: dict(base_input) for step in steps}

    rid = run_id or f"lokay-{uuid.uuid4().hex[:12]}"
    # Ensure organ imports resolve from checkout when not fully installed
    root = _project_root()
    src = root / "src"
    if src.is_dir():
        prev = os.environ.get("PYTHONPATH", "")
        if str(src) not in prev.split(os.pathsep):
            os.environ["PYTHONPATH"] = str(src) + (os.pathsep + prev if prev else "")

    # Fala Mojo sources (editable path dep sibling ../Fala)
    if not os.environ.get("FALA_HOME"):
        for candidate in (
            root.parent / "Fala",
            Path.cwd().parent / "Fala",
            Path("/Users/mikomac/Developer/OSS/Fala"),
        ):
            if (candidate / "mojo" / "fala").is_dir():
                os.environ["FALA_HOME"] = str(candidate.resolve())
                break

    result = host_run_package(
        db_path=db,
        package_path=pkg_runtime,
        path_id=path_id,
        run_id=rid,
        effector_inputs=effector_inputs,
        max_ticks=max_ticks,
        worker_id="lokay-graph",
    )
    return {
        "ok": bool(result.get("ok")),
        "engine": "fala",
        "path_id": path_id,
        "package": str(pkg_runtime),
        "db": str(db),
        "run_id": rid,
        "repo": repo,
        "issue": issue,
        "live": live,
        "fala": result,
    }


def describe_package(package_path: str | Path | None = None) -> dict[str, Any]:
    """Parse graph structure without running (order inspection)."""
    try:
        import tomllib
    except ImportError:  # pragma: no cover
        import tomli as tomllib  # type: ignore

    pkg = Path(package_path) if package_path else find_default_package()
    data = tomllib.loads(pkg.read_text(encoding="utf-8"))
    paths = []
    for path in data.get("correlation_paths") or []:
        effectors = path.get("effectors") or []
        nodes = []
        for eff in effectors:
            nodes.append(
                {
                    "id": eff.get("id"),
                    "atom": (eff.get("config") or {}).get("atom"),
                    "conduction": list(eff.get("conduction") or []),
                }
            )
        paths.append({"id": path.get("id"), "title": path.get("title"), "nodes": nodes})
    return {"package_id": data.get("id"), "paths": paths}
