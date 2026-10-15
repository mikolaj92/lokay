import re
from dataclasses import dataclass
from pathlib import Path

from lokay.lint import diff_lines, lint_diff, unit_test_files


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


def ok(name: str) -> dict:
    return {"name": name, "pass": True, "reason": "stub", "location": None, "fix_hint": ""}


def evidence(name: str, passed: bool, reason: str, failures: list[dict], limit: int,
             log: str, fix_hint: str) -> dict:
    details = "; ".join(
        f"{item.get('warstwa', '')}: {item.get('log', '')[-limit:]}" for item in failures
    ) or log[-limit:]
    first = failures[0] if failures else {}
    location = first.get("plik") or first.get("warstwa") or None
    if first.get("plik") and first.get("linia") is not None:
        location = f"{location}:{first['linia']}"
    return {"name": name, "pass": passed, "reason": reason + (f": {details}" if details else ""),
            "location": location, "fix_hint": "" if passed else fix_hint + (f": {details}" if details else "")}


def ci_green(x: CheckInput) -> dict:
    passed = x.ci.get("sha") == x.sha and x.ci.get("ci") in ("green", "no_ci")
    failures = [item for item in x.ci.get("failed", []) if item.get("warstwa") == "GitHub CI"]
    return evidence("ci_green", passed,
                    f"GitHub CI {x.ci.get('ci')} at {x.ci.get('sha')}; expected green or no_ci at {x.sha}",
                    failures, 3000, "", "run and fix GitHub CI for the current SHA")


def local_tests(x: CheckInput) -> dict:
    failures = [item for item in x.ci.get("failed", []) if item.get("warstwa") != "GitHub CI"]
    github_failed = any(item.get("warstwa") == "GitHub CI" for item in x.ci.get("failed", []))
    green = x.ci.get("result") == "green" or (x.ci.get("result") == "red" and github_failed)
    passed = x.ci.get("sha") == x.sha and x.ci.get("tested") is True and green and not failures
    reason = "local tests green" if passed else "local tests not green or not run"
    timeout = next((item["timeout"] for item in failures if item.get("timeout") is not None), None)
    if not passed and timeout is not None:
        reason = f"tests timed out after {timeout} s"
    if passed and x.ci.get("baseline"):
        reason = f"no new local test failures against main at {x.ci['baseline']['sha']}"
    return evidence("local_tests", passed, reason, failures, 800,
                    "" if passed else x.ci.get("log", ""), "run and fix the complete local test suite")


def merge_clean(x: CheckInput) -> dict:
    return ok("merge_clean")


def plan_files(x: CheckInput) -> dict:
    return ok("plan_files")


def lockfile(x: CheckInput) -> dict:
    return ok("lockfile")


def secrets(x: CheckInput) -> dict:
    return ok("secrets")


def permissions(x: CheckInput) -> dict:
    return ok("permissions")


def no_new_comments(x: CheckInput) -> dict:
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
        return {"name": "no_new_comments", "pass": False,
                "reason": "; ".join(errors), "location": errors[0].split(": ", 1)[0],
                "fix_hint": "; ".join(errors)}
    return {**ok("no_new_comments"), "reason": "no new comments or lint errors"}


def no_unit_tests(x: CheckInput) -> dict:
    paths = unit_test_files(x.diff)
    if paths:
        return {"name": "no_unit_tests", "pass": False,
                "reason": "new unit tests: " + ", ".join(paths), "location": paths[0],
                "fix_hint": "add a replay fixture under fixtures/replay"}
    return {**ok("no_unit_tests"), "reason": "no new unit tests"}


def issue_goal(x: CheckInput) -> dict:
    return ok("issue_goal")


def scope(x: CheckInput) -> dict:
    return ok("scope")


def correctness(x: CheckInput) -> dict:
    return ok("correctness")


def tests_cover(x: CheckInput) -> dict:
    return ok("tests_cover")


def regression(x: CheckInput) -> dict:
    return ok("regression")


def architecture(x: CheckInput) -> dict:
    return ok("architecture")


def security_review(x: CheckInput) -> dict:
    return ok("security_review")


def docs(x: CheckInput) -> dict:
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
        return {**ok("docs"), "reason": "requested documentation changes match the plan"}
    if offenders:
        path, change = offenders[0]
        return {"name": "docs", "pass": False,
                "reason": "documentation expanded without request or plan: " + "; ".join(
                    f"{path}: +{change['net']} net lines" for path, change in offenders),
                "location": f"{path}:{change['line']}",
                "fix_hint": "trim only these expanded files: " + ", ".join(
                    path for path, _ in offenders)
                + "; never delete documentation that the issue or plan requires"}
    return {**ok("docs"), "reason": "no documentation expansion"}


def style(x: CheckInput) -> dict:
    return ok("style")


CHECKS = [ci_green, local_tests, merge_clean, plan_files, lockfile, secrets, permissions, no_new_comments, no_unit_tests,
          issue_goal, scope, correctness, tests_cover, regression, architecture,
          security_review, docs, style]


def run_checks(x: CheckInput) -> dict:
    results = []
    for check in CHECKS:
        try:
            results.append(check(x))
        except Exception as exc:
            results.append({"name": check.__name__, "pass": False,
                            "reason": f"{type(exc).__name__}: {exc}", "location": None,
                            "fix_hint": "check crashed; fix the check or its input"})
    failed = [r for r in results if not r["pass"]]
    verdict = {"result": "merge" if not failed else "fix", "sha": x.sha, "checks": results, "failed": failed}
    return verdict
