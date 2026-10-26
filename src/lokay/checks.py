import ast
import os
import re
import shlex
import shutil
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import unquote

from lokay.gates import dead_test_candidates, dead_tests, moved_test_candidates, moved_tests, named_test
from lokay.lint import diff_lines, lint_diff, unit_test_hints
from lokay.scope import ASSERTION, is_artifact, is_test, kind as change_kind
from lokay.types import CheckResult, Finding, parse_finding


@dataclass
class CheckInput:
    repo: str
    issue: int
    sha: str
    issue_body: str
    plan: str
    diff: str
    hunks: list[dict]
    ci: dict
    worktree: Path
    title: str = ""
    red_main: bool = False
    main: dict | None = None


def evidence(name: str, passed: bool, reason: str, failures: list[dict],
             log: str, fix_hint: str) -> CheckResult:
    details = "; ".join(
        f"{item.get('warstwa', '')}: {item.get('log', '')}" for item in failures
    ) or log
    findings = []
    if not passed:
        for failure in failures:
            item = parse_finding(failure)
            if isinstance(item, Finding):
                line = item.linia_od or int(failure.get("linia") or 1)
                findings.append(Finding(item.plik, line, item.linia_do or line,
                                        fix_hint + (f": {details}" if details else ""), name))
    return CheckResult(name, "pass" if passed else "fail",
                       reason + (f": {details}" if details else ""), tuple(findings))


def ci_green(x: CheckInput) -> CheckResult:
    if x.ci.get("sha") == x.sha and x.ci.get("ci") == "inherited" and x.ci.get("inherited"):
        inherited = x.ci["inherited"]
        details = "; ".join(f"{item['check']}: {', '.join(item['steps'])}" for item in inherited)
        return CheckResult("ci_green", "pass",
                           f"GitHub checks fail only on steps that also fail on fresh main {inherited[0]['main_sha']}: {details}", ())
    if x.ci.get("ci") == "no_ci" and x.ci.get("sha") == x.sha:
        return CheckResult("ci_green", "pass", "not applicable: no CI configured", ())
    if x.ci.get("ci") in (None, "pending") and x.ci.get("sha") == x.sha:
        return CheckResult("ci_green", "unknown", f"GitHub CI {x.ci.get('ci')}: no completed check runs", ())
    passed = x.ci.get("sha") == x.sha and x.ci.get("ci") == "green"
    failures = [item for item in x.ci.get("failed", []) if item.get("warstwa") == "GitHub CI"]
    return evidence("ci_green", passed,
                    f"GitHub CI {x.ci.get('ci')} at {x.ci.get('sha')}; expected green or no_ci at {x.sha}",
                    failures, "", "run and fix GitHub checks for the current SHA")


def local_tests(x: CheckInput) -> CheckResult:
    failures = [item for item in x.ci.get("failed", []) if item.get("warstwa") != "GitHub CI"]
    github_failed = any(item.get("warstwa") == "GitHub CI" for item in x.ci.get("failed", []))
    green = x.ci.get("result") == "green" or (x.ci.get("result") == "red" and github_failed)
    passed = x.ci.get("sha") == x.sha and x.ci.get("tested") is True and green and not failures
    if not x.ci.get("tested") and not failures:
        return CheckResult("local_tests", "unknown", "local tests not run", ())
    if passed:
        executed = x.ci.get("executed", 0)
        if executed > 0:
            return CheckResult("local_tests", "pass", f"{executed} passed", ())
        if x.ci.get("syntax_only"):
            return CheckResult("local_tests", "pass", "syntax only (repos.yaml syntax_only: true)", ())
        return CheckResult("local_tests", "unknown", "exit 0 but no executed test count in log", ())
    reason = "local tests not green or not run"
    if baseline := x.ci.get("baseline"):
        reason += (f"; main {baseline['sha']}, command {baseline.get('argv')}: "
                   f"same failures {baseline.get('inherited', [])}; remaining failures are not on main")
    timeout = next((item["timeout"] for item in failures if item.get("timeout") is not None), None)
    if not passed and timeout is not None:
        reason = f"tests timed out after {timeout} s"
    return evidence("local_tests", passed, reason, failures,
                    "" if passed else x.ci.get("log", ""), "run and fix the complete local test suite")


def merge_clean(x: CheckInput) -> CheckResult:
    from lokay.effects.git import merge_conflicts

    paths = merge_conflicts(x.worktree, x.sha)
    findings = tuple(Finding(path, 1, 1, "resolve merge conflict", "merge_clean") for path in paths)
    return CheckResult("merge_clean", "fail" if findings else "pass",
                       "merge conflicts found" if findings else "merge is clean", findings)


def secrets(x: CheckInput) -> CheckResult:
    pattern = re.compile(
        r"AKIA[A-Z0-9]{16}|(?:ghp_|gho_|github_pat_)[A-Za-z0-9_]+"
        r"|-----BEGIN (?:[^\r\n]* )?PRIVATE KEY-----|xox[abp]-[A-Za-z0-9-]+"
        r"|(?i:api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{20,})"
    )
    findings = tuple(
        Finding(path, number, number, "possible secret", "secrets")
        for path, number, kind, text in diff_lines(x.diff)
        if kind == "+" and pattern.search(text)
    )
    return CheckResult("secrets", "fail" if findings else "pass",
                       "possible secret" if findings else "no secrets found", findings)


def _revisions(x):
    from lokay.effects.git import base_branch, git_try

    try:
        code, base, _ = git_try(x.worktree, "merge-base", x.sha, "origin/" + base_branch(x.worktree))
        if code:
            return None
        base = base.strip()
        code, base_paths, _ = git_try(x.worktree, "ls-tree", "-r", "--name-only", base)
        if code:
            return None
        code, head_paths, _ = git_try(x.worktree, "ls-tree", "-r", "--name-only", x.sha)
        if code:
            return None

        def source(revision, path):
            try:
                code, text, _ = git_try(x.worktree, "show", f"{revision}:{path}")
                return None if code else text
            except Exception:
                return None

        return (base_paths.splitlines(), head_paths.splitlines(),
                lambda path: source(base, path), lambda path: source(x.sha, path))
    except Exception:
        return None


def _moved(x):
    if moved_test_candidates(x.diff):
        revisions = _revisions(x)
        if revisions is not None:
            return moved_tests(x.diff, *revisions)
    return {"names": {}, "added": {}, "removed": {}}


def no_new_comments(x: CheckInput) -> CheckResult:
    ignored = {".md", ".rst", ".txt", ".json", ".lock"}
    markers = {
        "#": {".py", ".pyi", ".sh", ".bash", ".zsh", ".fish", ".rb", ".pl", ".pm", ".ps1", ".r", ".jl", ".ex", ".exs", ".mojo", ".🔥", ".php", ".tcl", ".yaml", ".yml", ".toml", ""},
        "//": {".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".java", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".swift", ".kt", ".kts", ".scala", ".php", ".dart", ".zig", ".vue", ".svelte"},
        "--": {".sql", ".lua", ".hs", ".elm", ".adb", ".ads"},
        ";": {".lisp", ".cl", ".clj", ".cljs", ".scm", ".el", ".asm", ".s"},
        "<!--": {".html", ".htm", ".xml", ".svg", ".vue", ".svelte"},
    }
    markers["/*"] = markers["//"] | {".css", ".scss", ".sass", ".sql"}
    markers["*"] = markers["/*"]
    offenders = []
    for path, number, kind, text in diff_lines(x.diff):
        suffix = Path(path).suffix.lower()
        if kind != "+" or suffix == ".py" or suffix in ignored:
            continue
        stripped = text.strip()
        if stripped.startswith("#!"):
            continue
        if suffix in {".py", ".pyi"} and re.match(
            r"#\s*(?:.*?coding[:=]\s*[-\w.]+|type\s*:|noqa\b)", stripped, re.IGNORECASE
        ):
            continue
        comment = any(stripped.startswith(marker) and suffix in extensions
                      for marker, extensions in markers.items())
        if comment:
            offenders.append((f"{path}:{number}", stripped))
    errors = lint_diff(x.diff, x.sha, x.worktree, lokay_rules=x.repo.rsplit("/", 1)[-1] == "lokay",
                       neutral=_moved(x)["added"])
    errors.extend(f"{location}: added comment -> remove it" for location, _ in offenders)
    if errors:
        findings = []
        for error in errors:
            location, _, hint = error.partition(": ")
            path, separator, line = location.rpartition(":")
            number = int(line) if separator and line.isdecimal() else 1
            findings.append(Finding(path if separator and line.isdecimal() else location,
                                    number, number, hint, "no_new_comments"))
        return CheckResult("no_new_comments", "fail", "; ".join(errors), tuple(findings))
    return CheckResult("no_new_comments", "pass", "no new comments or lint errors", ())


def no_unit_tests(x: CheckInput) -> CheckResult:
    paths = unit_test_hints(x.diff, neutral=_moved(x)["added"])
    if paths:
        first_added = {}
        for path, number, kind, _ in diff_lines(x.diff):
            if kind == "+":
                first_added.setdefault(path, number)
        return CheckResult("no_unit_tests", "fail", "new unit tests: " + ", ".join(paths), tuple(
            Finding(path, first_added.get(path, 1), first_added.get(path, 1),
                    "add a replay fixture under fixtures/replay" if x.repo.rsplit("/", 1)[-1] == "lokay" else hint,
                    "no_unit_tests") for path, hint in paths.items()))
    return CheckResult("no_unit_tests", "pass", "no new unit tests", ())


def deleted_files(x: CheckInput) -> CheckResult:
    deleted = set()
    for block in x.diff.split("diff --git ")[1:]:
        header = block.split("\n@@ ", 1)[0].splitlines()
        if not any(line.startswith("deleted file mode ") for line in header):
            continue
        match = re.fullmatch(r'("a/(?:\\.|[^"])*"|a/.*?) ("b/(?:\\.|[^"])*"|b/.*)', header[0])
        if match is None:
            raise ValueError("invalid diff path")
        path = ast.literal_eval(match[1]) if match[1].startswith('"') else match[1]
        deleted.add(path.removeprefix("a/"))
    unapproved = sorted(path for path in deleted if not any(
        re.search(r"(?<![\w./-])" + re.escape(name) + r"(?![\w./-])", text)
        for name in (path, Path(path).name) for text in (x.issue_body, x.plan)))
    if unapproved:
        reason = (f"deleted files not named by the issue or plan: {len(unapproved)} "
                  f"({', '.join(unapproved[:5])})")
        return CheckResult("deleted_files", "fail", reason, tuple(
            Finding(path, 1, 1, reason, "deleted_files") for path in unapproved))
    return CheckResult("deleted_files", "pass",
                       "deleted files named by the issue or plan" if deleted else "no deleted files", ())


def weakened_tests(x: CheckInput) -> CheckResult:
    from lokay.config import repo as repo_config
    from lokay.effects.tests import base_tests_on_head

    changed = set()
    for block in x.diff.split("diff --git ")[1:]:
        header = block.split("\n@@ ", 1)[0].splitlines()
        if any(line.startswith("new file mode ") for line in header):
            continue
        match = re.fullmatch(r'("a/(?:\\.|[^"])*"|a/.*?) ("b/(?:\\.|[^"])*"|b/.*)', header[0])
        if match is None:
            raise ValueError("invalid diff path")
        path = match[1]
        if path.startswith('"'):
            path = ast.literal_eval(path)
        path = path.removeprefix("a/")
        if Path(path).is_absolute() or ".." in Path(path).parts:
            continue
        lines = [text for _, _, kind, text in diff_lines("diff --git " + block) if kind in {"-", "+"}]
        if is_test(path, lines):
            changed.add(path)
    moved = _moved(x)
    for path in sorted(changed):
        lines = [(number, kind, text) for p, number, kind, text in diff_lines(x.diff)
                 if p == path and kind in {"+", "-"}]
        if (lines and all(number in moved["added"].get(path, ()) for number, kind, _ in lines if kind == "+")
                and Counter(text for _, kind, text in lines if kind == "-") <= moved["removed"].get(path, Counter())):
            changed.remove(path)
    dead = frozenset()
    if dead_test_candidates(x.diff, moved["names"]):
        revisions = _revisions(x)
        if revisions is not None:
            try:
                dead = dead_tests(x.diff, x.issue_body, *revisions, moved=moved["names"])
            except Exception:
                dead = frozenset()
    changed -= dead
    unapproved = sorted(path for path in changed if not named_test(path, x.issue_body))
    if unapproved:
        reason = "existing test changed but the issue body does not name it: " + ", ".join(unapproved)
        findings = tuple(Finding(path, 1, 1, reason, "weakened_tests") for path in unapproved)
        return CheckResult("weakened_tests", "fail", reason, findings)
    if not changed:
        return CheckResult("weakened_tests", "pass", "no existing tests changed", ())
    config = repo_config(x.repo)
    if x.ci.get("result") != "green" or not config.get("test") or config.get("syntax_only"):
        return _count_weakened_tests(x, dead, moved)
    paths = sorted(changed)
    result = base_tests_on_head(x.worktree, x.sha, paths, config, x.issue)
    if result.get("result") == "green":
        counted = _count_weakened_tests(x, dead, moved)
        if counted.status == "fail":
            return counted
        return CheckResult("weakened_tests", "pass",
                           "base versions of changed tests pass on the new code: " + ", ".join(paths), ())
    return _count_weakened_tests(x, dead, moved)


def _count_weakened_tests(x: CheckInput, dead=frozenset(), moved=None) -> CheckResult:
    moved = moved or {"added": {}, "removed": {}}
    changes = {}
    for path, number, kind, text in diff_lines(x.diff):
        if (path not in dead and kind in {"-", "+"} and ASSERTION.match(text)
                and not (kind == "+" and number in moved["added"].get(path, ()))):
            change = changes.setdefault(path, {"-": [], "+": []})
            change[kind].append((number, text))
    findings = []
    reasons = []
    for path, change in changes.items():
        removed = len(change["-"]) - len(change["+"]) - sum(
            count for text, count in moved["removed"].get(path, {}).items() if ASSERTION.match(text))
        if removed > 0 and is_test(path, [text for lines in change.values() for _, text in lines]):
            reason = f"Removes {removed} test assertions: {path}"
            line = max(1, change["-"][0][0])
            reasons.append(reason)
            findings.append(Finding(path, line, line, reason, "weakened_tests"))
    return CheckResult("weakened_tests", "fail" if findings else "pass",
                       "; ".join(reasons) if findings else "no test assertions removed", tuple(findings))


def encoded_rewrite(x: CheckInput) -> CheckResult:
    findings = []
    for block in re.split(r"(?m)(?=^diff --git )", x.diff):
        header, *hunks = re.split(r"(?m)(?=^@@ )", block)
        for hunk in hunks:
            removed = set()
            added = []
            for path, number, kind, text in diff_lines(header + hunk):
                if kind == "-":
                    removed.add(text)
                elif kind == "+":
                    added.append((path, number, text))
            for path, number, text in added:
                decoded = unquote(text)
                if decoded != text and decoded in removed:
                    findings.append(Finding(path, number, number,
                                            "Text was percent-encoded instead of changed; keep the original or make a real change.",
                                            "encoded_rewrite"))
    return CheckResult("encoded_rewrite", "fail" if findings else "pass",
                       "percent-encoded rewrites found" if findings else "no percent-encoded rewrites", tuple(findings))


def intent(x: CheckInput) -> CheckResult:
    from lokay.review import docs_only

    signals = [tag for tag in ("[code-audit]", "[test-audit]") if tag in x.title.lower()]
    if x.red_main:
        signals.append("red main")
    if signals and x.diff and docs_only(x.diff):
        paths = sorted({token[2:] for line in x.diff.splitlines() if line.startswith("diff --git ")
                        for token in shlex.split(line)[2:]})
        findings = tuple(Finding(path, 1, 1,
                                 "issue needs a code change; implement it instead of editing docs", "intent")
                         for path in paths)
        return CheckResult("intent", "fail", "docs/plan only instead of code: " + ", ".join(signals), findings)
    return CheckResult("intent", "pass", "no code intent mismatch", ())


def docs(x: CheckInput) -> CheckResult:
    changes = {}
    for path, number, kind, text in diff_lines(x.diff):
        file = Path(path)
        if change_kind([path]) != "docs":
            continue
        if not (x.worktree / file).resolve().is_relative_to(x.worktree.resolve()):
            continue
        change = changes.setdefault(path, {"net": 0, "line": None})
        if kind == "+":
            change["net"] += 1
            if change["line"] is None:
                change["line"] = number
        elif kind == "-":
            change["net"] -= 1
    expanded = [(path, change) for path, change in changes.items() if change["net"] > 0]
    if re.search(r"\b(?:dodaj\s+(?:sekcję|plik)|nowy\s+dokument|add\s+(?:a\s+)?(?:section|file|document))\b",
                 x.issue_body, re.IGNORECASE):
        return CheckResult("docs", "pass", "explicit request to add a document or section", ())
    if sum(change["net"] for change in changes.values()) > 0:
        return CheckResult("docs", "fail", "documentation expanded: " + "; ".join(
            f"{path}: +{change['net']} net lines" for path, change in expanded), tuple(
                Finding(path, change["line"], change["line"], "shorten: docs must not grow", "docs")
                for path, change in expanded))
    return CheckResult("docs", "pass", "no documentation expansion", ())


def lockfile(x: CheckInput) -> CheckResult:
    from lokay.build import LOCKFILES
    from lokay.effects.tests import check_uv_lock

    root = x.worktree.resolve()
    drifted = set()
    for line in x.ci.get("log", "").splitlines():
        if not line.startswith("lockfile drift: "):
            continue
        path = Path(line.removeprefix("lockfile drift: "))
        if (path.is_absolute() or ".." in path.parts or path.name not in LOCKFILES
                or not (root / path).resolve().is_relative_to(root)):
            continue
        drifted.add(path.as_posix())
    errors = []
    locks = []
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=errors.append):
        dirs[:] = sorted(name for name in dirs if name not in {".venv", "node_modules", ".git"}
                         and not (Path(directory) / name).is_symlink())
        if "uv.lock" in files and "pyproject.toml" in files:
            locks.append(Path(directory) / "uv.lock")
    available = shutil.which("uv") is not None
    if available:
        for path in sorted(locks):
            status, reason = check_uv_lock(path.parent)
            if status == "fail":
                drifted.add(path.relative_to(root).as_posix())
            elif status == "unknown":
                errors.append(f"{path.relative_to(root)}: {reason}")
    inherited = set()
    if x.main and x.main.get("lockfile", {}).get("status") == "fail":
        inherited = {f["plik"] for f in x.main["lockfile"]["findings"]}
    inherited_drift = drifted & inherited
    drifted -= inherited
    if drifted:
        message = "uv.lock is out of date with pyproject.toml: run `uv lock`"
        findings = tuple(Finding(name, 1, 1, message if Path(name).name == "uv.lock" else
                                 "lockfile drift during setup or tests: review and commit the lockfile",
                                 "lockfile") for name in sorted(drifted))
        return CheckResult("lockfile", "fail", "; ".join(sorted(drifted)) + ": " + message, findings)
    if locks and not available:
        errors.append("uv lock checks unavailable: uv not found")
    if errors:
        return CheckResult("lockfile", "unknown", "; ".join(map(str, errors)), ())
    if inherited_drift:
        return CheckResult("lockfile", "pass",
                           "; ".join(sorted(inherited_drift)) + f": drift inherited from red main {x.main['sha']}", ())
    reason = "uv unavailable" if not available else "uv lock checks passed" if locks else "no applicable uv locks"
    return CheckResult("lockfile", "pass", reason, ())


def _diff_path(block: str) -> str | None:
    lines = block.splitlines()
    header = re.search(r' ("b/(?:\\.|[^"])*"|b/.*)$', lines[0]) if lines else None
    if header is None:
        return None
    path = header[1]
    if path.startswith('"'):
        path = ast.literal_eval(path)
    for line in lines[1:]:
        if line.startswith("+++ "):
            target = line[4:].split("\t", 1)[0]
            if target.startswith('"'):
                target = ast.literal_eval(target)
            if target != "/dev/null":
                path = target
            break
    return path.removeprefix("b/")


def junk(x: CheckInput) -> CheckResult:
    paths = set()
    for block in x.diff.split("diff --git ")[1:]:
        lines = block.splitlines()
        if any(line.startswith("deleted file mode ") for line in lines):
            continue
        path = _diff_path(block)
        if path is None:
            raise ValueError("invalid diff path")
        if Path(path).is_absolute() or ".." in Path(path).parts:
            continue
        if is_artifact(path, x.worktree):
            paths.add(path)
    findings = tuple(Finding(path, 1, 1, "remove generated junk file", "junk") for path in sorted(paths))
    return CheckResult("junk", "fail" if findings else "pass",
                       "generated junk files: " + ", ".join(sorted(paths)) if findings else "no generated junk files",
                       findings)


CHECKS = [ci_green, local_tests, merge_clean, lockfile, secrets, junk,
          no_new_comments, no_unit_tests, weakened_tests, deleted_files, encoded_rewrite, intent, docs]


def run_checks(x: CheckInput) -> tuple[CheckResult, ...]:
    blocks = x.diff.split("diff --git ")
    filtered = replace(x, diff=blocks[0] + "".join(
        "diff --git " + block for block in blocks[1:]
        if (path := _diff_path(block)) is None or not is_artifact(path, x.worktree)))
    results = []
    for check in CHECKS:
        try:
            results.append(check(x if check is junk else filtered))
        except Exception as exc:
            results.append(CheckResult(check.__name__, "fail",
                                       f"{type(exc).__name__}: {exc}; check crashed; fix the check or its input", ()))
    return tuple(results)
