import re
from dataclasses import dataclass
from pathlib import Path

from lokay.lint import diff_lines, lint_diff, unit_test_files
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
    if x.ci.get("ci") in (None, "no_ci", "pending") and x.ci.get("sha") == x.sha:
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
        notes = [item for item in x.ci.get("notes", []) if item.get("warstwa") == "tests"]
        if (x.ci.get("sha") == x.sha and x.ci.get("result") == "green"
                and x.ci.get("tested") is False and notes
                and all(item.get("log") == "no tests configured" for item in notes)):
            return CheckResult("local_tests", "pass", "not applicable: no tests configured", ())
        return CheckResult("local_tests", "unknown", "local tests not run", ())
    reason = "local tests green" if passed else "local tests not green or not run"
    timeout = next((item["timeout"] for item in failures if item.get("timeout") is not None), None)
    if not passed and timeout is not None:
        reason = f"tests timed out after {timeout} s"
    if passed and x.ci.get("baseline"):
        reason = f"no new local test failures against main at {x.ci['baseline']['sha']}"
    return evidence("local_tests", passed, reason, failures, 800,
                    "" if passed else x.ci.get("log", ""), "run and fix the complete local test suite")


def no_new_comments(x: CheckInput) -> CheckResult:
    ignored = {".md", ".rst", ".txt", ".json", ".yaml", ".yml", ".toml", ".lock"}
    markers = {
        "#": {".py", ".pyi", ".sh", ".bash", ".zsh", ".fish", ".rb", ".pl", ".pm", ".ps1", ".r", ".jl", ".ex", ".exs", ".mojo", ".php", ".tcl", ""},
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
        if kind != "+" or suffix == ".py" or suffix in ignored or "docs" in Path(path).parts[:-1]:
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
        return CheckResult("no_unit_tests", "fail", "new unit tests: " + ", ".join(paths), tuple(
            Finding(path, 1, 1, "add a replay fixture under fixtures/replay", "no_unit_tests") for path in paths))
    return CheckResult("no_unit_tests", "pass", "no new unit tests", ())


def docs(x: CheckInput) -> CheckResult:
    changes = {}
    for path, number, kind, text in diff_lines(x.diff):
        file = Path(path)
        if file.suffix.lower() not in {".md", ".rst", ".txt"} and "docs" not in file.parts[:-1]:
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
    requested = re.search(
        r"\b(?:README|docs|ADR|RFC|design\s+doc\w*|projekt\w*|dokument\w*|documentation|decyzj\w*|guide|changelog)\b",
        x.issue_title + "\n" + x.issue_body, re.IGNORECASE)
    unplanned = [(path, change) for path, change in expanded if not any(
        re.search(r"(?<![\w./-])" + re.escape(candidate) + r"/?(?![\w./-])", x.plan)
        for candidate in (path, str(Path(path).parent)) if candidate != ".")]
    offenders = unplanned if requested else expanded
    if expanded and not offenders:
        return CheckResult("docs", "pass", "requested documentation changes match the plan", ())
    if offenders:
        hint = "trim only these expanded files: " + ", ".join(path for path, _ in offenders)
        hint += "; never delete documentation that the issue or plan requires"
        return CheckResult("docs", "fail", "documentation expanded without request or plan: " + "; ".join(
            f"{path}: +{change['net']} net lines" for path, change in offenders), tuple(
                Finding(path, change["line"], change["line"], hint, "docs") for path, change in offenders))
    return CheckResult("docs", "pass", "no documentation expansion", ())


CHECKS = [ci_green, local_tests, "merge_clean", "plan_files", "lockfile", "secrets", "permissions",
          no_new_comments, no_unit_tests, "issue_goal", "scope", "correctness", "tests_cover", "regression",
          "architecture", "security_review", docs, "style"]


def verdict(results: tuple[CheckResult, ...], ci: dict | None = None) -> dict:
    failed = tuple(result for result in results if result.status != "pass" and not (
        result.status == "unknown" and result.name == "ci_green" and ci is not None and ci.get("ci") == "no_ci"))
    return {"result": "fix" if failed else "merge", "checks": results, "failed": failed}


def run_checks(x: CheckInput) -> tuple[CheckResult, ...]:
    results = []
    for check in CHECKS:
        if isinstance(check, str):
            results.append(CheckResult(check, "pass", "stub", ()))
            continue
        try:
            results.append(check(x))
        except Exception as exc:
            results.append(CheckResult(check.__name__, "fail",
                                       f"{type(exc).__name__}: {exc}; check crashed; fix the check or its input", ()))
    return tuple(results)
