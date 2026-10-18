import ast
import os
import re
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from lokay.lint import diff_lines, lint_diff, unit_test_files
from lokay.scope import ASSERTION, is_artifact, is_cache, is_test, kind as change_kind, legacy_planned_files, matches_path, planned_files, required_files
from lokay.types import CheckResult, Finding, parse_finding


@dataclass
class CheckInput:
    repo: str
    issue: int
    sha: str
    issue_title: str
    issue_body: str
    plan: str
    diff: str
    hunks: list[dict]
    ci: dict
    worktree: Path
    plan_schema: int | None = None


def evidence(name: str, passed: bool, reason: str, failures: list[dict], limit: int,
             log: str, fix_hint: str) -> CheckResult:
    details = "; ".join(
        f"{item.get('warstwa', '')}: {item.get('log', '')[-limit:]}" for item in failures
    ) or log[-limit:]
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
    if x.ci.get("ci") == "no_ci" and x.ci.get("sha") == x.sha:
        return CheckResult("ci_green", "pass", "not applicable: no CI configured", ())
    if x.ci.get("ci") in (None, "pending") and x.ci.get("sha") == x.sha:
        return CheckResult("ci_green", "unknown", f"GitHub CI {x.ci.get('ci')}: no completed check runs", ())
    passed = x.ci.get("sha") == x.sha and x.ci.get("ci") == "green"
    failures = [item for item in x.ci.get("failed", []) if item.get("warstwa") == "GitHub CI"]
    return evidence("ci_green", passed,
                    f"GitHub CI {x.ci.get('ci')} at {x.ci.get('sha')}; expected green or no_ci at {x.sha}",
                    failures, 3000, "", "run and fix GitHub CI for the current SHA")


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
    timeout = next((item["timeout"] for item in failures if item.get("timeout") is not None), None)
    if not passed and timeout is not None:
        reason = f"tests timed out after {timeout} s"
    return evidence("local_tests", passed, reason, failures, 800,
                    "" if passed else x.ci.get("log", ""), "run and fix the complete local test suite")


def merge_clean(x: CheckInput) -> CheckResult:
    from lokay.effects.git import merge_conflicts

    paths = merge_conflicts(x.worktree, x.sha)
    findings = tuple(Finding(path, 1, 1, "resolve merge conflict", "merge_clean") for path in paths)
    return CheckResult("merge_clean", "fail" if findings else "pass",
                       "merge conflicts found" if findings else "merge is clean", findings)


def secrets(x: CheckInput) -> CheckResult:
    pattern = re.compile(
        r"(?<![A-Za-z0-9_])(?:AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{36}"
        r"|github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}"
        r"|xox[bap]-[0-9]{10,13}-[0-9]{10,13}-[A-Za-z0-9]{24,32})(?![A-Za-z0-9_])"
        r"|-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
    )
    findings = tuple(
        Finding(path, number, number, f"secrets at {x.sha}: remove added secret", "secrets")
        for path, number, kind, text in diff_lines(x.diff)
        if kind == "+" and pattern.search(text)
    )
    return CheckResult("secrets", "fail" if findings else "pass",
                       f"secrets at {x.sha}: possible secret" if findings else "no secrets found", findings)


def no_new_comments(x: CheckInput) -> CheckResult:
    ignored = {".md", ".rst", ".txt", ".json", ".lock"}
    markers = {
        "#": {".py", ".pyi", ".sh", ".bash", ".zsh", ".fish", ".rb", ".pl", ".pm", ".ps1", ".r", ".jl", ".ex", ".exs", ".mojo", ".php", ".tcl", ".yaml", ".yml", ".toml", ""},
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
    errors = lint_diff(x.diff, x.sha, x.worktree, lokay_rules=x.repo.rsplit("/", 1)[-1] == "lokay")
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
    paths = unit_test_files(x.diff)
    if paths:
        first_added = {}
        for path, number, kind, _ in diff_lines(x.diff):
            if kind == "+":
                first_added.setdefault(path, number)
        return CheckResult("no_unit_tests", "fail", "new unit tests: " + ", ".join(paths), tuple(
            Finding(path, first_added.get(path, 1), first_added.get(path, 1),
                    "add a replay fixture under fixtures/replay", "no_unit_tests") for path in paths))
    return CheckResult("no_unit_tests", "pass", "no new unit tests", ())


def weakened_tests(x: CheckInput) -> CheckResult:
    deleted = set()
    for block in x.diff.split("diff --git ")[1:]:
        header = block.split("\n@@ ", 1)[0].splitlines()
        if "+++ /dev/null" in header:
            deleted.update(path for path, _, _, _ in diff_lines("diff --git " + block))
    planned = planned_files(x.plan, [], sorted(deleted))
    changes = {}
    for path, number, kind, text in diff_lines(x.diff):
        if kind in {"-", "+"} and ASSERTION.match(text):
            change = changes.setdefault(path, {"-": [], "+": []})
            change[kind].append((number, text))
    findings = []
    reasons = []
    for path, change in changes.items():
        if path in deleted and any(matches_path(path, target) for target in planned):
            continue
        removed = len(change["-"]) - len(change["+"])
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
        if "pyproject.toml" in files:
            manifest = Path(directory) / "pyproject.toml"
            try:
                data = tomllib.loads(manifest.read_text())
                if "uv.lock" in files or "project" in data or "uv" in data.get("tool", {}):
                    locks.append(manifest.with_name("uv.lock"))
            except (OSError, ValueError) as exc:
                errors.append(f"{manifest.relative_to(root)}: {type(exc).__name__}")
    available = shutil.which("uv") is not None
    for path in sorted(locks):
        status, _ = check_uv_lock(path.parent) if available else ("fail", "uv unavailable")
        if status != "pass":
            drifted.add(path.relative_to(root).as_posix())
    if drifted:
        message = f"lockfile at {x.sha}: uv lock --check failed; run `uv lock` or repair the tool"
        findings = tuple(Finding(name, 1, 1, message if Path(name).name == "uv.lock" else
                                 "lockfile drift during setup or tests: review and commit the lockfile",
                                 "lockfile") for name in sorted(drifted))
        return CheckResult("lockfile", "fail", "; ".join(sorted(drifted)) + ": " + message, findings)
    if errors:
        message = f"lockfile at {x.sha}: cannot inspect manifests"
        return CheckResult("lockfile", "fail", message, (
            Finding("pyproject.toml", 1, 1, message, "lockfile"),))
    return CheckResult("lockfile", "pass" if locks else "skip",
                       "uv lock checks passed" if locks else "no applicable uv project", ())


def junk(x: CheckInput) -> CheckResult:
    paths = set()
    for block in x.diff.split("diff --git ")[1:]:
        lines = block.splitlines()
        if any(line.startswith("deleted file mode ") for line in lines):
            continue
        header = re.search(r' ("b/(?:\\.|[^"])*"|b/.*)$', lines[0])
        if header is None:
            raise ValueError("invalid diff path")
        path = header[1]
        if path.startswith('"'):
            path = ast.literal_eval(path)
        path = path.removeprefix("b/")
        for line in lines[1:]:
            if line.startswith("+++ "):
                path = line[4:].split("\t", 1)[0]
                if path.startswith('"'):
                    path = ast.literal_eval(path)
                path = path.removeprefix("b/")
                break
        if Path(path).is_absolute() or ".." in Path(path).parts:
            continue
        if is_artifact(path, x.worktree):
            paths.add(path)
    findings = tuple(Finding(path, 1, 1, "remove generated junk file", "junk") for path in sorted(paths))
    return CheckResult("junk", "fail" if findings else "pass",
                       "generated junk files: " + ", ".join(sorted(paths)) if findings else "no generated junk files",
                       findings)


def plan_target(x: CheckInput) -> CheckResult:
    changed = set()
    deletions_only = True
    for block in x.diff.split("diff --git ")[1:]:
        lines = block.splitlines()
        header = re.fullmatch(r'("a/(?:\\.|[^"])*"|a/.*?) ("b/(?:\\.|[^"])*"|b/.*)', lines[0])
        if header is None:
            raise ValueError("invalid diff path")
        paths = [(path, True) for path in header.groups()]
        for line in lines[1:]:
            if line.startswith(("--- ", "+++ ")):
                paths.append((line[4:].split("\t", 1)[0], True))
            elif line.startswith(("rename from ", "rename to ")):
                paths.append((line.split(" ", 2)[2], False))
        for path, prefixed in paths:
            if path.startswith('"'):
                path = ast.literal_eval(path)
            if prefixed and path.startswith(("a/", "b/")):
                path = path[2:]
            if path != "/dev/null" and not Path(path).is_absolute() and ".." not in Path(path).parts:
                changed.add(path)
        removed = any(line.startswith("-") and not line.startswith("--- ") for line in lines[1:])
        added = any(line.startswith("+") and not line.startswith("+++ ") for line in lines[1:])
        deleted = any(line.startswith("deleted file mode ") for line in lines[1:])
        metadata = any(line.startswith(("rename ", "copy ", "old mode ", "new mode ",
                                        "Binary files ", "GIT binary patch")) for line in lines[1:])
        if not deleted and (not removed or added or metadata):
            deletions_only = False
    repo_files = []
    for directory, dirs, files in os.walk(x.worktree, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name != ".git" and not is_cache(name)
                         and not (Path(directory) / name).is_symlink())
        repo_files.extend((Path(directory) / name).relative_to(x.worktree).as_posix() for name in files)
    parser = planned_files if x.plan_schema == 2 else legacy_planned_files
    planned = parser(x.plan, repo_files, sorted(changed))
    code = {path for path in planned if not is_test(path) and not path.startswith("docs/")
            and Path(path).suffix.lower() not in (".md", ".rst", ".txt")}
    missing = sorted(target for target in required_files(x.plan, repo_files, sorted(changed))
                     if not any(matches_path(path, target) for path in changed)) if x.plan_schema == 2 else []
    goal = re.search(r"^## Cel\s*\n(.*?)(?=^## |\Z)", x.plan, re.M | re.S)
    addition = re.search(r"\b(?:add(?:s|ed|ing)?|doda[cć]\w*|dodaj\w*|uzupełni\w*)\b",
                         goal[1] if goal else "", re.IGNORECASE)
    reasons = []
    if not changed:
        reasons.append("Empty diff")
    if x.plan_schema == 2:
        from lokay.plan import valid_plan_text

        if not valid_plan_text(x.plan, x.plan_schema):
            reasons.append("PLAN ERROR: invalid version-2 files list; redo Plan")
        if missing:
            reasons.append("Required planned files missing from the diff: " + ", ".join(missing))
    elif code and not any(matches_path(path, target) for path in changed for target in code):
        reasons.append("Diff does not touch any planned code file: " + ", ".join(sorted(code)))
    if changed and deletions_only and addition:
        reasons.append("Deletions-only diff does not implement planned additions")
    reason = "; ".join(reasons) if reasons else "diff touches planned files"
    path = next(iter(missing or sorted(code) or sorted(planned) or sorted(changed)), "plan.md")
    findings = (Finding(path, 1, 1, reason, "plan_target"),) if reasons else ()
    return CheckResult("plan_target", "fail" if reasons else "pass", reason, findings)


CHECKS = [ci_green, local_tests, merge_clean, lockfile, secrets, junk,
          no_new_comments, no_unit_tests, weakened_tests, encoded_rewrite, docs, plan_target]


def run_checks(x: CheckInput) -> tuple[CheckResult, ...]:
    results = []
    for check in CHECKS:
        try:
            results.append(check(x))
        except Exception as exc:
            results.append(CheckResult(check.__name__, "fail",
                                       f"{type(exc).__name__}: {exc}; check crashed; fix the check or its input", ()))
    return tuple(results)
