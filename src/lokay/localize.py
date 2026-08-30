"""Deterministic fallback localization: seed text + repo tree → edit paths.

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
# Worktree leftover names encode the mill issue: ai/fix/333-… or ai__fix__333-…
_WORKTREE_ISSUE_RE = re.compile(r"(?:ai(?:/|__)fix(?:/|__))(\d+)(?:-|$)")

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

# Tokens / identifiers from seed text (not a full stopword list).
# 2+ letter ALLCAPS first so TK/SN survive; then identifiers / CamelCase.
_TOKEN_RE = re.compile(
    r"\b([A-Z]{2,}|[A-Za-z_][A-Za-z0-9_]{2,}|[A-Z][a-z]+(?:[A-Z][a-z0-9]+)*)\b"
)
# One-letter platform names (X) are real stems. Do not generalize to A/I.
_STANDALONE_PLATFORM_RE = re.compile(r"\bX\b")
_PLATFORM_ALIASES = {
    "x": ("twitter", "tweet"),
}
_PATHISH_RE = re.compile(
    r"(?<![`\w])((?:[\w.-]+/)+[\w.-]+(?:\.[A-Za-z0-9]{1,12})?)"
)
_FILES_HEADING_RE = re.compile(r"(?im)^\s*#{1,6}\s+files?\s*:?[ \t]*$")
_LOCALIZATION_HEADING_RE = re.compile(
    r"(?im)^\s*#{1,6}\s+(?:zmiana|files?)\s*:?[ \t]*$"
)
_ANY_HEADING_RE = re.compile(r"(?im)^\s*#{1,6}\s+.+$")
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
        "proc",
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
        # Polish prose (ticket bodies are often PL; these are not edit stems).
        "nie",
        "tak",
        "jest",
        "sa",
        "są",
        "byc",
        "być",
        "jak",
        "czy",
        "ale",
        "lub",
        "oraz",
        "gdy",
        "gdyz",
        "gdyż",
        "zeby",
        "żeby",
        "jesli",
        "jeśli",
        "ktory",
        "który",
        "ktore",
        "które",
        "tego",
        "tym",
        "tej",
        "ten",
        "ta",
        "to",
        "sie",
        "się",
        "bez",
        "przy",
        "przez",
        "poza",
        "nad",
        "pod",
        "ma",
        "mam",
        "mamy",
        "mieć",
        "miec",
        "trzeba",
        "moze",
        "może",
        "musi",
        "musza",
        "muszą",
        "zostawic",
        "zostawić",
        "trzymac",
        "trzymać",
        "pusty",
        "pusta",
        # Planning / spec noise — token match, not a ship path.
        "plan",
        "planning",
        "specs",
        "spec",
        "roadmap",
        "audit",
        "audits",
    }
)

# Weak token hits below this do not pad the list to _MAX_PATHS.
_MIN_INFERRED_SCORE = 30

# Top-level dirs that are layout, not the product package name.
_GENERIC_TOP_DIRS = frozenset(
    {
        "src",
        "tests",
        "test",
        "docs",
        "fala",
        "scripts",
        "config",
        "lib",
        "bin",
        "pkg",
        "cmd",
        "internal",
        "vendor",
        "examples",
        "example",
        "fixtures",
        "testdata",
        ".github",
        ".lokay",
    }
)

# ``Repository: owner/name`` / github.com/owner/name in approach.md or issue.
_REPO_SLUG_RE = re.compile(
    r"(?:Repository:|github\.com/)\s*`?[\w.-]+/([\w.-]+)",
    re.IGNORECASE,
)

# Directory / filename stems that are planning evidence, not edit targets.
_DEMOTE_DIR_PARTS = frozenset(
    {
        "planning",
        "specs",
        "audits",
        "docs",
        "notes",
        "tasks",
    }
)
_DEMOTE_FILE_NAMES = frozenset({"plan.md", "readme.md", "agents.md"})

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
    semantic: dict[str, Any] | None = None
    issue: int = 0

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


def localization_seed_text(text: str) -> str:
    """Limit a structured issue seed to its declared change/file sections.

    Counterexamples and off-goal notes often contain valid-looking paths.  Once
    an issue declares ``Zmiana`` or ``Files``, only those sections are edit
    evidence; unstructured seeds retain the historical behavior.
    """
    blob = text or ""
    headings = list(_LOCALIZATION_HEADING_RE.finditer(blob))
    if not headings:
        return blob
    sections: list[str] = []
    for heading in headings:
        next_heading = _ANY_HEADING_RE.search(blob, heading.end())
        end = next_heading.start() if next_heading else len(blob)
        sections.append(blob[heading.start() : end])
    return "\n\n".join(sections)


def extract_seed_paths(text: str) -> tuple[str, ...]:
    """Explicit path-like strings from the localization-relevant seed."""
    blob = localization_seed_text(text)
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


def has_issue_files_section(body: str) -> bool:
    """Whether an issue body explicitly declares a ``Files`` section."""
    return bool(_FILES_HEADING_RE.search(body or ""))


def extract_issue_file_paths(body: str) -> tuple[str, ...]:
    """Extract paths from an issue's explicit change/file sections."""
    text = body or ""
    found: list[str] = []
    headings = list(_LOCALIZATION_HEADING_RE.finditer(text))
    if headings:
        found.extend(extract_seed_paths(text))
    else:
        # A path at the start of a markdown bullet is an explicit file hint
        # when the issue omits a structured localization section.
        for line in text.splitlines():
            if re.match(r"^\s*[-*+]\s+(?:\[[ xX]\]\s*)?(?:`|(?:\*\*)?)(?:src|tests|docs|fala|scripts|config)/", line):
                found.extend(extract_seed_paths(line))
    return tuple(dict.fromkeys(found))


def extract_seed_tokens(text: str) -> tuple[str, ...]:
    """Meaningful identifiers from localization-relevant seed text."""
    text = localization_seed_text(text)
    tokens: list[str] = []
    for match in _TOKEN_RE.finditer(text):
        tok = match.group(1)
        low = tok.lower()
        if low in _STOP_TOKENS:
            continue
        if tok.isdigit():
            continue
        # 2-letter ALLCAPS (TK, SN) are stems; other 2-letter tokens are noise.
        if len(tok) < 2 or (len(tok) == 2 and not tok.isupper()):
            continue
        tokens.append(tok)
    if _STANDALONE_PLATFORM_RE.search(text or ""):
        tokens.append("X")
    # path stems as tokens too
    for path in extract_seed_paths(text or ""):
        for part in path.replace(".", "/").split("/"):
            if len(part) >= 3 and part.lower() not in _STOP_TOKENS:
                tokens.append(part)
    return tuple(dict.fromkeys(tokens))


def _repo_name_tokens(
    seed_text: str,
    *,
    worktree: Path | None = None,
) -> set[str]:
    """Checkout / package name is not an edit stem (influenzer#137)."""
    names: set[str] = set()
    for match in _REPO_SLUG_RE.finditer(seed_text or ""):
        slug = match.group(1).strip().lower().rstrip(".git")
        if slug and slug not in _GENERIC_TOP_DIRS:
            names.add(slug)
    if worktree is not None:
        for raw in (Path(worktree).name.lower(), Path(worktree).parent.name.lower()):
            if "__" not in raw:
                continue
            slug = raw.split("__", 1)[-1]
            if slug and slug not in _GENERIC_TOP_DIRS:
                names.add(slug)
    return names


def _score_path(
    rel: str,
    tokens_lower: set[str],
    explicit: set[str],
    *,
    ignore_tokens: set[str] | None = None,
    worktree: Path | None = None,
    content_needles: set[str] | None = None,
) -> int:
    if rel in explicit:
        return 1000
    score = 0
    parts = rel.replace("\\", "/").split("/")
    stem = Path(rel).stem.lower()
    name = Path(rel).name.lower()
    lowered_parts = [p.lower() for p in parts]
    ignore = {t.lower() for t in (ignore_tokens or ()) if t}
    for tok in tokens_lower:
        if tok in ignore:
            continue
        if tok == stem or tok == name or tok == Path(rel).name:
            score += 50
        elif tok in lowered_parts:
            score += 30
        elif tok in stem.split("_") or tok in stem.split("-"):
            # scan_due.py ← token `scan` is the same hit as a directory named scan.
            score += 30
        elif len(tok) <= 2:
            # `x` is a letter in influenzer/unrelated — not a path hit.
            continue
        elif any(tok in p for p in lowered_parts):
            score += 10
        elif tok in rel.lower():
            score += 5
    if (
        worktree is not None
        and content_needles
        and rel not in explicit
        and _path_has_content_needles(Path(worktree), rel, content_needles)
    ):
        # X → twitter/tweet in file body is a real stem, not a letter in the path.
        score += 30
    # Prefer source / tests over docs and lockfiles.
    if parts and parts[0] in {"src", "tests", "fala", "scripts", "config"}:
        score += 8
    is_test = name.startswith("test_") or "/tests/" in f"/{rel}/"
    if is_test:
        score += 12
    elif score > 0:
        # A product file with a real token hit must clear the inferred
        # floor alongside its tests. Otherwise `gate`/`scan` cages the
        # agent in tests/ and the mill records plan_only.
        score += 12
    if rel.endswith((".py", ".mojo", ".toml", ".yaml", ".yml", ".sh")):
        score += 4
    elif rel.endswith(".md"):
        score -= 8
    if name in _DEMOTE_FILE_NAMES or any(p in _DEMOTE_DIR_PARTS for p in lowered_parts):
        score -= 40
    return score


def _expand_platform_tokens(tokens_lower: set[str]) -> tuple[set[str], set[str]]:
    """X is twitter/tweet in product files, not a one-letter substring."""
    needles: set[str] = set()
    expanded = set(tokens_lower)
    for tok in tokens_lower:
        aliases = _PLATFORM_ALIASES.get(tok)
        if not aliases:
            continue
        expanded.update(aliases)
        needles.update(aliases)
    return expanded, needles


def _seed_identifier_needles(tokens: Iterable[str]) -> set[str]:
    """Snake identifiers from the seed (`has_fair_hook`) live in product files."""
    return {tok.lower() for tok in tokens if "_" in tok}


def _is_docs_rel(rel: str) -> bool:
    name = Path(rel).name.lower()
    parts = Path(rel).as_posix().split("/")
    return name.endswith(".md") or parts[:1] == ["docs"] or parts[:1] == ["skills"]


def _path_has_content_needles(worktree: Path, rel: str, needles: set[str]) -> bool:
    if not needles:
        return False
    try:
        raw = (Path(worktree) / rel).read_bytes()
    except OSError:
        return False
    text = raw.decode("utf-8", errors="ignore").lower()
    return any(needle in text for needle in needles)


def _is_test_rel(rel: str) -> bool:
    name = Path(rel).name.lower()
    return name.startswith("test_") or "/tests/" in f"/{rel}/"


def _product_stem_from_test(rel: str) -> str:
    stem = Path(rel).stem.lower()
    return stem[5:] if stem.startswith("test_") else ""


_IMPORT_RE = re.compile(
    r"^(?:from|import)\s+([A-Za-z_][\w.]*)",
    re.MULTILINE,
)


def _first_party_imports(abs_path: Path, tree_set: set[str]) -> tuple[str, ...]:
    """Map `from pkg.mod import x` to an existing repo-relative product file."""
    try:
        text = abs_path.read_text(encoding="utf-8")
    except OSError:
        return ()
    found: list[str] = []
    for mod in _IMPORT_RE.findall(text):
        root = mod.split(".", 1)[0]
        if root in {
            "__future__",
            "tests",
            "typing",
            "pathlib",
            "unittest",
            "json",
            "io",
            "os",
            "sys",
            "re",
            "ast",
            "collections",
            "contextlib",
            "datetime",
            "tempfile",
            "tomllib",
        }:
            continue
        rel = mod.replace(".", "/")
        for cand in (f"{rel}.py", f"{rel}/__init__.py"):
            if cand in tree_set and not _is_test_rel(cand):
                found.append(cand)
                break
        if len(found) >= 8:
            break
    return tuple(dict.fromkeys(found))


def _attach_product_paths(
    selected: list[str],
    *,
    tree_list: list[str],
    worktree: Path | None,
    max_paths: int,
) -> list[str]:
    """A tests-only inferred scope is a cage. Open the matching product files."""
    tree_set = set(tree_list)
    extra: list[str] = []
    for rel in selected:
        if not _is_test_rel(rel):
            continue
        stem = _product_stem_from_test(rel)
        paired: list[str] = []
        if stem:
            for cand in tree_list:
                if _is_test_rel(cand):
                    continue
                if Path(cand).stem.lower() == stem:
                    paired.append(cand)
        extra.extend(paired)
    selected_plus = (*selected, *extra)
    has_code_product = any(
        not _is_test_rel(p) and not _is_docs_rel(p) for p in selected_plus
    )
    if not has_code_product and worktree is not None:
        root = Path(worktree)
        for rel in selected:
            if not _is_test_rel(rel):
                continue
            extra.extend(_first_party_imports(root / rel, tree_set))
    out = list(dict.fromkeys([p for p in extra if p] + selected))
    product = [p for p in out if not _is_test_rel(p)]
    tests = [p for p in out if _is_test_rel(p)]
    return list(dict.fromkeys(product + tests))[:max_paths]


def select_paths(
    *,
    tree: Iterable[str],
    seed_text: str,
    extra_paths: Iterable[str] = (),
    max_paths: int = _MAX_PATHS,
    worktree: Path | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Return (paths, seed_paths, matched_tokens)."""
    explicit = list(extract_seed_paths(seed_text))
    explicit.extend(_norm_rel(p) for p in extra_paths if _norm_rel(p))
    explicit_set = set(dict.fromkeys(p for p in explicit if p))
    tokens = extract_seed_tokens(seed_text)
    tokens_lower = {t.lower() for t in tokens}
    tokens_lower, content_needles = _expand_platform_tokens(tokens_lower)
    content_needles = set(content_needles) | _seed_identifier_needles(tokens)
    ignore_tokens = _repo_name_tokens(seed_text, worktree=worktree)

    tree_list = [_norm_rel(p) for p in tree if _norm_rel(p)]
    tree_set = set(tree_list)

    scored: list[tuple[int, str]] = []
    for rel in tree_list:
        s = _score_path(
            rel,
            tokens_lower,
            explicit_set,
            ignore_tokens=ignore_tokens,
            worktree=worktree,
            content_needles=content_needles,
        )
        if s > 0:
            scored.append((s, rel))
    scored.sort(key=lambda x: (-x[0], x[1]))

    selected: list[str] = []
    # Always include explicit paths that exist or are path-like (even if not yet created).
    for rel in explicit:
        if rel and rel not in selected:
            selected.append(rel)
    # Inferred hits must clear a floor. Weak substring matches must not pad
    # the list to max_paths — a 40-path "scope" is a cage, not a compass.
    for score, rel in scored:
        if rel in selected:
            continue
        if score < _MIN_INFERRED_SCORE:
            continue
        selected.append(rel)
        if len(selected) >= max_paths:
            break

    selected = _attach_product_paths(
        selected,
        tree_list=tree_list,
        worktree=worktree,
        max_paths=max_paths,
    )

    # If still empty, try directory-level matches from tokens against top-level tree.
    # Repo / package name is not a directory hit — that is the whole product.
    if not selected and tokens_lower:
        usable = {t for t in tokens_lower if t not in ignore_tokens}
        for rel in tree_list:
            base = rel.split("/", 1)[0].lower()
            if base in _GENERIC_TOP_DIRS or base in ignore_tokens:
                continue
            if base in usable or any(t in base for t in usable if len(t) >= 4):
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
    """Pure fallback localization from seed + optional worktree tree."""
    notes: list[str] = [
        "Deterministic fallback paths only (no embeddings).",
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
        worktree=Path(worktree) if worktree is not None else None,
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


def _positive_issue(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
        return number if number > 0 else None
    return None


def issue_from_localize_payload(raw: dict[str, Any]) -> int | None:
    """Issue this localize.json belongs to, or None if missing/unparseable."""
    for key in ("issue", "issue_number"):
        owned = _positive_issue(raw.get(key))
        if owned is not None:
            return owned
    worktree = str(raw.get("worktree") or "").replace("\\", "/")
    match = _WORKTREE_ISSUE_RE.search(worktree)
    if match:
        return int(match.group(1))
    return None


def load_existing_localize_paths(
    worktree: Path | None,
    *,
    rel_path: str = LOCALIZE_REL_PATH,
    issue: int | None = None,
) -> list[str]:
    """Non-empty paths already written for this issue, if any.

    A file inherited from main (other issue in ``worktree``, missing issue id,
    or leftover from another ticket) is not a sieve. A same-issue list with a
    missing file or non-path token is also not a sieve.
    """
    if worktree is None:
        return []
    current = _positive_issue(issue)
    if current is None:
        return []
    path = Path(worktree) / rel_path
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(raw, dict):
        return []
    owned = issue_from_localize_payload(raw)
    if owned is None or owned != current:
        return []
    rows = raw.get("paths") or []
    if not isinstance(rows, list):
        return []
    out: list[str] = []
    for item in rows:
        rel = _norm_rel(str(item or ""))
        if rel and ".." not in rel.split("/"):
            out.append(rel)
    unique = list(dict.fromkeys(out))
    if not unique:
        return []
    root = Path(worktree)
    # Same-issue evidence is a sieve only when every path exists.
    # A version token or vanished file is leftover, not a cage.
    if any(not (root / rel).exists() for rel in unique):
        return []
    return unique


def localize_belongs_to_issue(
    worktree: Path | None,
    issue: int | None,
    *,
    rel_path: str = LOCALIZE_REL_PATH,
) -> bool | None:
    """Whether localize.json is this issue's sieve.

    ``True``: payload belongs to this issue (``load_existing_localize_paths``
    would accept it, including empty paths).
    ``False``: readable leftover — other issue, missing id, or inherited #333.
    ``None``: missing worktree or unreadable file (fail-closed).
    """
    current = _positive_issue(issue)
    if worktree is None or current is None:
        return None
    path = Path(worktree) / rel_path
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    owned = issue_from_localize_payload(raw)
    if owned is None or owned != current:
        return False
    load_existing_localize_paths(Path(worktree), rel_path=rel_path, issue=current)
    return True


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
