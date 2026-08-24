"""Fala bindings for authored declared local-test execution."""

from typing import Any


def handle_test_local(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    inspected = up.get("inspect_test_declaration") or {}
    if atom == "inspect_test_declaration":
        from lokay.proc.inspect_test_declaration import inspect

        return inspect(worktree=str(inputs.get("worktree") or ""))
    if atom == "read_test_green_cache":
        from lokay.proc.read_test_green_cache import read

        return read(inspected)
    if atom == "run_declared_tests":
        from lokay.proc.run_declared_test_command import run

        return run(inspected, list(inspected.get("test_argv") or []))
    if atom == "select_declared_test_outcome":
        from lokay.proc.select_declared_test_outcome import select

        return select(
            up.get("run_declared_tests") or {},
            changed_scope=bool(inputs.get("changed_scope")),
        )
    if atom == "derive_changed_test_scope":
        from lokay.proc.derive_changed_test_scope import derive

        return derive(inspected, up.get("select_declared_test_outcome") or {})
    if atom == "run_changed_scope_tests":
        from lokay.proc.run_declared_test_command import run

        return run(
            inspected,
            list((up.get("derive_changed_test_scope") or {}).get("argv") or []),
        )
    if atom == "select_green_test_result":
        from lokay.proc.select_green_test_result import select

        return select(
            up.get("run_declared_tests") or {}, up.get("run_changed_scope_tests") or {}
        )
    if atom == "write_test_green_cache":
        from lokay.proc.write_test_green_cache import write

        return write(
            inspected,
            up.get("read_test_green_cache") or {},
            up.get("select_green_test_result") or {},
        )
    if atom == "classify_test_terminal":
        from lokay.proc.classify_test_terminal import classify

        return classify(
            inspected,
            up.get("read_test_green_cache") or {},
            up.get("run_declared_tests") or {},
            up.get("run_changed_scope_tests") or {},
            up.get("write_test_green_cache") or {},
        )
    if atom.startswith("build_test_terminal_"):
        from lokay.proc import build_test_terminal

        builders = {
            "inspection": lambda: build_test_terminal.inspection(inspected),
            "cached": lambda: build_test_terminal.cached(
                inspected, up.get("read_test_green_cache") or {}
            ),
            "green": lambda: build_test_terminal.green(
                inspected,
                up.get("run_declared_tests") or {},
                up.get("run_changed_scope_tests") or {},
                up.get("write_test_green_cache") or {},
            ),
            "red": lambda: build_test_terminal.red(
                inspected,
                up.get("run_declared_tests") or {},
                up.get("run_changed_scope_tests") or {},
            ),
        }
        return builders[atom.rsplit("_", 1)[1]]()
    if atom == "select_test_terminal":
        from lokay.proc.select_test_terminal import select

        return select(
            [
                up.get(f"build_test_terminal_{kind}") or {}
                for kind in ("inspection", "cached", "green", "red")
            ]
        )
    return None
