#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run python - <<'PY'
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from lokay.check import aggregate, local_ci
from lokay.gh import pr_checks

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "code.py").write_text("def value(): return 42\n")
    (root / "verify.py").write_text("from code import value\nassert value() == 42\n")
    request = {"repo": "example/repo", "pr": 7, "sha": "head-a", "cwd": tmp,
               "test": [[sys.executable, "-B", "verify.py"]]}
    view = {"headRefOid": "head-a", "statusCheckRollup": [
        {"name": "verify", "status": "COMPLETED", "conclusion": "SUCCESS"}]}
    def gh(args):
        assert args[:3] == ["pr", "view", "7"]
        return 0, json.dumps(view), ""
    def check():
        ci = local_ci(request["sha"], request["test"], request["cwd"])
        with patch("lokay.gh._gh", gh):
            remote = pr_checks(request["repo"], request["pr"], request["sha"])
        if remote["result"] in ("pending", "sha_moved"):
            return {**ci, "result": remote["result"], "head_sha": remote["sha"]}
        ci["failed"].extend({"warstwa": "GitHub CI", "plik": "", "log": name}
                            for name in remote.get("failed") or [])
        ci["result"] = "red" if ci["failed"] else "green"
        return ci

    assert check()["result"] == "green"
    # The PR mutation must be rejected even when GitHub and the model approve it.
    (root / "code.py").write_text("def value(): return 0\n")
    request["sha"] = view["headRefOid"] = "head-b"
    red = check()
    assert red["result"] == "red" and not red["failed"][0]["flaky"], red
    assert aggregate("head-b", red, [{"next": "ok"}])["result"] == "fix"
    (root / "code.py").write_text("def value(): return 42\n")
    (root / "verify.py").write_text(
        "from pathlib import Path\nfrom code import value\n"
        "p = Path('attempt')\nfirst = not p.exists()\np.touch()\n"
        "assert not first, 'transient failure'\nassert value() == 42\n")
    flaky = check()
    assert flaky["result"] == "green" and flaky["notes"][0]["flaky"], flaky
    verdict = aggregate("head-b", flaky, [{"next": "issue", "uwagi": [{"pytanie": "correctness"}]}])
    assert any(row.get("flaky") for row in verdict["uwagi"]), verdict
    view["statusCheckRollup"] = [{"context": "legacy", "state": "PENDING"}]
    pending = check()
    assert pending["result"] == "pending", pending
    assert aggregate("head-b", pending, [])['result'] == "check"
    view["statusCheckRollup"] = [{"context": "legacy", "state": "FAILURE"}]
    assert check()["result"] == "red"
    view["statusCheckRollup"] = [{"name": "verify", "status": "IN_PROGRESS", "conclusion": None}]
    assert check()["result"] == "pending"
    view["headRefOid"] = "head-c"
    moved = check()
    assert moved["result"] == "sha_moved" and moved["head_sha"] == "head-c", moved
    view["headRefOid"] = "head-b"
    request["test"] = []
    view["statusCheckRollup"] = []
    assert check()["result"] == "red"
print("CI: mutation red, retry/flaky, GitHub pending/red, SHA guard, empty tests red OK")
PY
