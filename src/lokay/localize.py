"""Deterministic Agentless-style localization: seed text + repo tree → edit paths.

One job only: produce a non-empty list of files/directories the coding agent
may patch. No embeddings, no second planner, no LLM step selection.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from lokay.approach_plan import extract_paths

LOCALIZE_REL_PATH = ".lokay/localize.json"

# Skip noise when walking the checkout.
_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        ".idea",
        ".vscode",
        ".cursor",
        "dist",
        "build",
        "target",
        "vendor",
        ".eggs",
        ".lokay",
    }
)
_SKIP_FILE_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".so",
    ".dylib",
    ".o",
    ".a",
    ".whl",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".lock",
)

# Tokens / identifiers from seed text (not full English stopword list).
_TOKEN_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{2,}|[A-Z][a-z]+(?:[A-Z][a-z0-9]+)*)\b")
_PATHISH_RE = re.compile(
    r"(?<![`\w])((?:[\w.-]+/)+[\w.-]+(?:\.[A-Za-z0-9]{1,12})?)"
)
_STOP_TOKENS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "when",
        "then",
        "than",
        "also",
        "only",
        "must",
        "should",
        "will",
        "not",
        "are",
        "was",
        "were",
        "been",
        "have",
        "has",
        "had",
        "but",
        "its",
        "our",
        "you",
        "your",
        "any",
        "all",
        "can",
        "may",
        "via",
        "per",
        "use",
        "using",
        "used",
        "add",
        "new",
        "fix",
        "bug",
        "issue",
        "test",
        "tests",
        "file",
        "files",
        "path",
        "paths",
        "repo",
        "code",
        "true",
        "false",
        "none",
        "null",
        "http",
        "https",
        "www",
        "com",
        "org",
        "github",
        "lokay",
        "agent",
        "python",
        "pytest",
        "goal",
        "summary",
        "approach",
        "notes",
        "scope",
        "body",
        "title",
        "main",
        "src",
        "docs",
        "scripts",
        "config",
        "data",
        "json",
        "yaml",
        "toml",
        "md",
        "txt",
        "run",
        "before",
        "after",
        "under",
        "over",
        "each",
        "once",
        "fail",
        "closed",
        "open",
        "list",
        "atom",
        "graph",
        "order",
        "step",
        "node",
        "pass",
        "mill",
        "tick",
        "live",
        "mode",
        "work",
        "tree",
        "branch",
        "commit",
        "push",
        "merge",
        "pull",
        "request",
        "check",
        "checks",
        "error",
        "errors",
        "failed",
        "failure",
        "local",
        "root",
        "dir",
        "dirs",
        "directory",
        "module",
        "modules",
        "package",
        "packages",
        "class",
        "function",
        "method",
        "return",
        "import",
        "from",
        "def",
        "class",
        "self",
        "type",
        "str",
        "int",
        "bool",
        "dict",
        "list",
        "set",
        "tuple",
        "path",
        "read",
        "write",
        "edit",
        "update",
        "create",
        "delete",
        "remove",
        "change",
        "changes",
        "patch",
        "diff",
        "line",
        "lines",
        "text",
        "content",
        "seed",
        "issue",
        "ticket",
        "task",
        "todo",
        "done",
        "ship",
        "implement",
        "implementation",
        "repair",
        "triage",
        "intake",
        "ready",
        "skip",
        "close",
        "human",
        "owner",
        "assignee",
        "label",
        "labels",
        "pr",
        "prs",
        "ci",
        "cd",
        "uv",
        "pip",
        "npm",
        "make",
        "bash",
        "shell",
        "cli",
        "api",
        "url",
        "http",
        "html",
        "css",
        "js",
        "ts",
        "py",
        "rs",
        "go",
        "java",
        "swift",
        "mojo",
        "fala",
    }
)

_MAX_WALK_ENTRIES = 8000
_MAX_PATHS = 40


@dataclass(frozen=True)
class Localization:
    paths: tuple[str, ...]
    source: str = "deterministic"
    seed_paths: tuple[str, ...] = ()
    matched_tokens: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    worktree: str = ""
    wrote: bool = False
    localize_rel: str = LOCALIZE_REL_PATH

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm_rel(raw: str) -> str:
    rel = str(raw or "").strip().replace("\\", "/").lstrip("./")
    while "//" in rel:
        rel = rel.replace("//", "/")
    return rel


def walk_repo_tree(worktree: Path, *, max_entries: int = _MAX_WALK_ENTRIES) -> tuple[str, ...]:
    """Relative file + directory paths under worktree (stable order)."""
    root = Path(worktree)
    if not root.is_dir():
        return ()
    found: list[str] = []
    try:
        for dirpath, dirnames, filenames in root.walk(top_down=True):
            # prune
            dirnames[:] = sorted(
                d
                for d in dirnames
                if d not in _SKIP_DIR_NAMES and not d.startswith(".git")
            )
            rel_dir = dirpath.relative_to(root).as_posix()
            if rel_dir != ".":
                found.append(rel_dir)
                if len(found) >= max_entries:
                    break
            for name in sorted(filenames):
                if name.startswith(".") and name not in {
                    ".gitignore",
                    ".gitattributes",
                    ".editorconfig",
                    ".env.example",
                }:
                    # keep common config; skip most dotfiles
                    if not name.startswith(".github"):
                        continue
                if name.endswith(_SKIP_FILE_SUFFIXES):
                    continue
                if name in {"uv.lock", "package-lock.json", "Cargo.lock"}:
                    continue
                rel = name if rel_dir == "." else f"{rel_dir}/{name}"
                found.append(rel)
                if len(found) >= max_entries:
                    break
            if len(found) >= max_entries:
                break
    except AttributeError:
        # Python <3.12 fallback (repo requires 3.12+, but keep simple).
        for path in sorted(root.rglob("*")):
            if any(part in _SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.is_file() and path.suffix in _SKIP_FILE_SUFFIXES:
                continue
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                continue
            found.append(rel)
            if len(found) >= max_entries:
                break
    return tuple(dict.fromkeys(found))


def _looks_like_repo_path(rel: str) -> bool:
    """Reject prose fragments and non-ASCII noise mistaken for paths."""
    if not rel or ".." in rel.split("/"):
        return False
    if any(ord(ch) > 127 for ch in rel):
        return False
    if rel.endswith(".") or rel.startswith(".") and "/" not in rel:
        return False
    parts = rel.split("/")
    if len(parts) < 2 and "." not in rel:
        return False
    # owner/repo style without extension is not an edit path
    if len(parts) == 2 and "." not in parts[-1] and parts[0] not in {
        "src",
        "tests",
        "docs",
        "fala",
        "scripts",
        "config",
        ".github",
        ".lokay",
    }:
        return False
    return True


def extract_seed_paths(text: str) -> tuple[str, ...]:
    """Explicit path-like strings from seed (issue/approach/checks)."""
    blob = text or ""
    found: list[str] = []
    found.extend(extract_paths(blob))
    for match in _PATHISH_RE.finditer(blob):
        found.append(match.group(1))
    # pytest / traceback style: File "…/src/x.py", line N
    for match in re.finditer(
        r'(?:File|file)\s+"([^"]+\.[A-Za-z0-9]{1,12})"',
        blob,
    ):
        found.append(match.group(1))
    for match in re.finditer(
        r"(?:^|\s)((?:src|tests|docs|fala|scripts|config)/[\w./-]+\.[A-Za-z0-9]{1,12})",
        blob,
        flags=re.MULTILINE,
    ):
        found.append(match.group(1))
    cleaned: list[str] = []
    for raw in found:
        rel = _norm_rel(raw).rstrip(".")
        # drop absolute host paths down to repo-relative when possible
        for marker in ("/src/", "/tests/", "/docs/", "/fala/", "/scripts/"):
            idx = rel.find(marker)
            if idx >= 0:
                rel = rel[idx + 1 :]
                break
        if _looks_like_repo_path(rel):
            cleaned.append(rel)
    return tuple(dict.fromkeys(cleaned))


def extract_seed_tokens(text: str) -> tuple[str, ...]:
    """Meaningful identifiers from seed text for tree matching."""
    tokens: list[str] = []
    for match in _TOKEN_RE.finditer(text or ""):
        tok = match.group(1)
        low = tok.lower()
        if low in _STOP_TOKENS:
            continue
        if tok.isdigit():
            continue
        if len(tok) < 3:
            continue
        tokens.append(tok)
    # path stems as tokens too
    for path in extract_seed_paths(text or ""):
        for part in path.replace(".", "/").split("/"):
            if len(part) >= 3 and part.lower() not in _STOP_TOKENS:
                tokens.append(part)
    return tuple(dict.fromkeys(tokens))


def _score_path(rel: str, tokens_lower: set[str], explicit: set[str]) -> int:
    if rel in explicit:
        return 1000
    score = 0
    parts = rel.replace("\\", "/").split("/")
    stem = Path(rel).stem.lower()
    name = Path(rel).name.lower()
    lowered_parts = [p.lower() for p in parts]
    for tok in tokens_lower:
        if tok == stem or tok == name or tok == Path(rel).name:
            score += 50
        elif tok in lowered_parts:
            score += 30
        elif any(tok in p for p in lowered_parts):
            score += 10
        elif tok in rel.lower():
            score += 5
    # Prefer source/tests over noise
    if parts and parts[0] in {"src", "tests", "docs", "fala", "scripts", "config"}:
        score += 3
    if rel.endswith((".py", ".toml", ".md", ".yaml", ".yml", ".sh", ".mojo")):
        score += 2
    return score


def select_paths(
    *,
    tree: Iterable[str],
    seed_text: str,
    extra_paths: Iterable[str] = (),
    max_paths: int = _MAX_PATHS,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Return (paths, seed_paths, matched_tokens)."""
    explicit = list(extract_seed_paths(seed_text))
    explicit.extend(_norm_rel(p) for p in extra_paths if _norm_rel(p))
    explicit_set = set(dict.fromkeys(p for p in explicit if p))
    tokens = extract_seed_tokens(seed_text)
    tokens_lower = {t.lower() for t in tokens}

    tree_list = [_norm_rel(p) for p in tree if _norm_rel(p)]
    tree_set = set(tree_list)

    scored: list[tuple[int, str]] = []
    for rel in tree_list:
        s = _score_path(rel, tokens_lower, explicit_set)
        if s > 0:
            scored.append((s, rel))
    scored.sort(key=lambda x: (-x[0], x[1]))

    selected: list[str] = []
    # Always include explicit paths that exist or are path-like (even if not yet created).
    for rel in explicit:
        if rel and rel not in selected:
            selected.append(rel)
    for _score, rel in scored:
        if rel in selected:
            continue
        selected.append(rel)
        if len(selected) >= max_paths:
            break

    # If still empty, try directory-level matches from tokens against top-level tree.
    if not selected and tokens_lower:
        for rel in tree_list:
            base = rel.split("/", 1)[0].lower()
            if base in tokens_lower or any(t in base for t in tokens_lower if len(t) >= 4):
                selected.append(rel.split("/", 1)[0])
                break

    # Prefer existing paths first, keep non-existing explicit last.
    existing = [p for p in selected if p in tree_set]
    missing = [p for p in selected if p not in tree_set]
    ordered = list(dict.fromkeys(existing + missing))[:max_paths]

    matched = tuple(
        t
        for t in tokens
        if any(t.lower() in p.lower() or t.lower() == Path(p).stem.lower() for p in ordered)
    )[:24]
    return tuple(ordered), tuple(dict.fromkeys(explicit)), matched


def build_localization(
    *,
    worktree: Path | None,
    seed_text: str,
    extra_paths: Iterable[str] = (),
    max_paths: int = _MAX_PATHS,
) -> Localization:
    """Pure localization from seed + optional worktree tree."""
    notes: list[str] = [
        "Agentless-style localization: deterministic paths only (no embeddings).",
        "Empty path list fails closed — run_agent must not start.",
    ]
    tree: tuple[str, ...] = ()
    wt = ""
    if worktree is not None and Path(worktree).is_dir():
        tree = walk_repo_tree(Path(worktree))
        wt = str(Path(worktree))
        notes.append(f"Repo tree entries considered: {len(tree)}.")
    else:
        notes.append("No worktree directory; using seed paths only.")

    paths, seed_paths, matched = select_paths(
        tree=tree,
        seed_text=seed_text or "",
        extra_paths=extra_paths,
        max_paths=max_paths,
    )
    if not paths:
        notes.append("No paths matched — fail closed.")
    return Localization(
        paths=paths,
        source="deterministic",
        seed_paths=seed_paths,
        matched_tokens=matched,
        notes=tuple(notes),
        worktree=wt,
    )


def write_localize_file(
    worktree: Path,
    localization: Localization,
    *,
    rel_path: str = LOCALIZE_REL_PATH,
) -> Path:
    path = Path(worktree) / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = localization.to_dict()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def render_paths_for_prompt(paths: Iterable[str]) -> str:
    items = [f"- `{_norm_rel(p)}`" for p in paths if _norm_rel(p)]
    if not items:
        return "- (none — agent must not start)"
    return "\n".join(items)
