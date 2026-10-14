from dataclasses import dataclass
from pathlib import Path


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


def ci_green(x: CheckInput) -> dict:
    return ok("ci_green")


def local_tests(x: CheckInput) -> dict:
    return ok("local_tests")


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
    return ok("docs")


def style(x: CheckInput) -> dict:
    return ok("style")


CHECKS = [ci_green, local_tests, merge_clean, plan_files, lockfile, secrets, permissions,
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
