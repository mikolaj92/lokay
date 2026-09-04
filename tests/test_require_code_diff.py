"""Hermetic tests for lokay.proc.require_code_diff (no git / Fala / organ)."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

from lokay.proc.require_code_diff import evaluate_names, main, parse_names

# Shape of lokay PRs #100 / #104 / #105: approach + localize only.
PLAN_ONLY = ".lokay/approach.md\n.lokay/localize.json\n"


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_parse_names_strips_and_dedupes():
    text = './src/a.py\n"tests/b.py"\n.src/skip\nsrc/a.py\n\n'
    assert parse_names(text) == ["src/a.py", "tests/b.py", ".src/skip"]


def test_evaluate_empty_is_plan_contract_fail():
    out = evaluate_names([])
    assert out["ok"] is False
    assert out["reason"] == "empty"
    assert out["code_paths"] == []


def test_evaluate_pr100_shape_is_plan_only():
    names = parse_names(PLAN_ONLY)
    out = evaluate_names(names)
    assert out["ok"] is False
    assert out["reason"] == "plan_only"
    assert out["plan_paths"] == [".lokay/approach.md", ".lokay/localize.json"]
    assert out["code_paths"] == []


def test_evaluate_code_roots_pass():
    for path in (
        "src/lokay/proc/require_code_diff.py",
        "tests/test_require_code_diff.py",
        "scripts/lokay-service.sh",
        "fala/lokay.fala-package.toml",
    ):
        out = evaluate_names([path])
        assert out["ok"] is True, path
        assert out["reason"] == "has_code"
        assert out["code_paths"] == [path]


def test_evaluate_mixed_plan_and_src_passes():
    out = evaluate_names(
        [".lokay/approach.md", "src/lokay/proc/foo.py", "README.md"]
    )
    assert out["ok"] is True
    assert out["code_paths"] == ["src/lokay/proc/foo.py"]
    assert out["plan_paths"] == [".lokay/approach.md"]
    assert out["other_paths"] == ["README.md"]


def test_evaluate_docs_only_has_no_code():
    out = evaluate_names(["docs/UNIX.md", "README.md"])
    assert out["ok"] is False
    assert out["reason"] == "no_code"
    assert out["other_paths"] == ["docs/UNIX.md", "README.md"]


def test_cli_stdin_plan_only_exits_2(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(PLAN_ONLY))
    code = main([])
    assert code == 2
    env = _payload(capsys)
    assert env["ok"] is False
    assert env["reason"] == "plan_only"


def test_cli_stdin_code_exits_0(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("src/lokay/x.py\n"))
    code = main([])
    assert code == 0
    env = _payload(capsys)
    assert env["ok"] is True
    assert env["code_paths"] == ["src/lokay/x.py"]


def test_cli_empty_stdin_exits_2(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    code = main([])
    assert code == 2
    env = _payload(capsys)
    assert env["reason"] == "empty"


def test_cli_names_file(tmp_path: Path, capsys):
    listing = tmp_path / "names.txt"
    listing.write_text("tests/test_x.py\n.lokay/approach.md\n", encoding="utf-8")
    code = main(["--names-file", str(listing)])
    assert code == 0
    env = _payload(capsys)
    assert env["ok"] is True
    assert env["code_paths"] == ["tests/test_x.py"]


def test_cli_missing_names_file_exits_1(tmp_path: Path, capsys):
    missing = tmp_path / "absent.txt"
    code = main(["--names-file", str(missing)])
    assert code == 1
    env = _payload(capsys)
    assert env["ok"] is False
    assert "cannot read --names-file" in env["error"]


def test_module_cli_python_dash_m(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    listing = tmp_path / "names.txt"
    listing.write_text(PLAN_ONLY, encoding="utf-8")
    env = dict(os.environ)
    src = str(root / "src")
    env["PYTHONPATH"] = src if not env.get("PYTHONPATH") else src + os.pathsep + env["PYTHONPATH"]
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "lokay.proc.require_code_diff",
            "--names-file",
            str(listing),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(root),
        env=env,
    )
    assert proc.returncode == 2
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["reason"] == "plan_only"
