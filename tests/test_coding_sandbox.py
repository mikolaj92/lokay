"""The coding seatbelt resolves a bare harness name on PATH, not against cwd."""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from lokay.coding_sandbox import coding_argv


def test_bare_command_resolves_on_path_not_cwd(tmp_path: Path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    harness = bindir / "pi"
    harness.write_text("#!/bin/sh\n")
    harness.chmod(harness.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "pi").write_text("not the harness\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}")

    argv, scratch = coding_argv(["pi", "--version"], worktree=tmp_path / "work")

    try:
        assert argv[0] == "/usr/bin/sandbox-exec"
        assert argv[argv.index("--") + 1] == str(harness.resolve())
    finally:
        import shutil
        shutil.rmtree(scratch, ignore_errors=True)


def test_bare_command_missing_from_path_stays_bare(tmp_path: Path, monkeypatch):
    """A name PATH does not carry is not resolved against cwd."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pi").write_text("not the harness\n")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    argv, scratch = coding_argv(["pi"], worktree=tmp_path)

    try:
        assert argv[argv.index("--") + 1] == "pi"
    finally:
        import shutil
        shutil.rmtree(scratch, ignore_errors=True)


def test_explicit_path_is_not_searched_on_path(tmp_path: Path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    decoy = bindir / "pi"
    decoy.write_text("#!/bin/sh\n")
    decoy.chmod(decoy.stat().st_mode | stat.S_IEXEC)
    named = tmp_path / "real-pi"
    named.write_text("#!/bin/sh\n")
    monkeypatch.setenv("PATH", str(bindir))

    argv, scratch = coding_argv([str(named)], worktree=tmp_path)

    try:
        assert argv[argv.index("--") + 1] == str(named.resolve())
    finally:
        import shutil
        shutil.rmtree(scratch, ignore_errors=True)
