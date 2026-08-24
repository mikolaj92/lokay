"""Purely identify protected Lokay-source residue not named by the issue."""

ALWAYS = (
    "src/lokay/proc/factory_begin.py",
    "src/lokay/proc/implement.py",
    "src/lokay/organ/agent.py",
    "fala/lokay.fala-package.toml",
    "src/lokay/data/lokay.fala-package.toml",
    "tests/test_hot_repos.py",
)


def classify(changed: dict, issue: dict) -> dict:
    explicit = set(issue.get("paths") or [])
    restore = [
        x
        for x in ALWAYS
        if x in set(changed.get("changed") or []) and x not in explicit
    ]
    return {
        "ok": True,
        "route": "restore" if restore else "continue",
        "restore_paths": restore,
    }
