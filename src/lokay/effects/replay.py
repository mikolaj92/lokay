from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack
from copy import deepcopy
from importlib import import_module
import os
from pathlib import Path
import re
import socket
from subprocess import CompletedProcess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
from typing import Any

from lokay import config, store
from lokay.replay import unpack
from lokay.types import Run, event_record


CHECK_HINTS = (
    ("remove the added test code; never remove, merge or weaken existing assertions",
     "make added non-blank lines <= removed non-blank lines in this file, or remove the added test code"),
    (r"\d+ more non-blank lines added than removed; blank lines do not count; (?:remove the added test code; never remove, merge or weaken existing assertions|make added non-blank lines <= removed non-blank lines in this file, or remove the added test code)",
     "keep the test change inside existing test functions with no net added lines, or remove the added test code"),
    ("new test file -> remove it; new test files are not allowed",
     "keep the test change inside existing test functions with no net added lines, or remove the added test code"),
    ("new unit test -> keep the test change inside existing test functions with no net added lines, or remove the added test code",
     "new unit test -> add a replay fixture under fixtures/replay and run uv run lokay replay"),
    ("keep the test change inside existing test functions with no net added lines, or remove the added test code",
     "add a replay fixture under fixtures/replay"),
)


class Mismatch(BaseException):
    pass


def stable(value):
    if isinstance(value, dict):
        return {key: stable(item) for key, item in value.items()
                if key not in {"ts", "updated_at", "node_since", "issue_since", "last_attempt",
                               "ladder_since", "diff_changed_at", "retry_at"}}
    if isinstance(value, list):
        return [stable(item) for item in value]
    return value


def compatible_checks(actual, expected) -> Any:
    if isinstance(actual, str) and isinstance(expected, str):
        for new, old in CHECK_HINTS:
            if old in expected or any(older in expected for newer, older in CHECK_HINTS if newer == old):
                actual = re.sub(new, lambda match: old, actual)
    if isinstance(actual, str) and isinstance(expected, str) and '"rule_id"' not in expected:
        actual = re.sub(r',?\n[ \t]*"rule_id": "[a-z_]+",?', '', actual)
    header = "| name | status | reason |\n| --- | --- | --- |\n"
    if isinstance(actual, str) and isinstance(expected, str) and header in actual and header in expected:
        prefix, _, tail = actual.partition(header)
        table, separator, suffix = tail.partition("\n\n")
        recorded = expected.partition(header)[2].partition("\n\n")[0].splitlines()
        names = {line.split(" | ", 2)[0] for line in recorded}
        table = "\n".join(line for line in table.splitlines()
                          if line.split(" | ", 2)[0] in names or line.split(" | ", 2)[1:2] != ["pass"])
        return prefix + header + table + separator + suffix
    if isinstance(actual, list) and isinstance(expected, list) and len(actual) == len(expected):
        return [compatible_checks(value, recorded) for value, recorded in zip(actual, expected)]
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return actual
    actual = actual.copy()
    if "rule_id" not in expected:
        actual.pop("rule_id", None)
    if "main_sha" not in expected and actual.get("main_sha") is None:
        actual.pop("main_sha", None)
    for key in actual.keys() & expected.keys():
        value, recorded = actual[key], expected[key]
        if key in {"checks", "results"} and isinstance(value, list) and isinstance(recorded, list):
            names = {item["name"] for item in recorded}
            actual[key] = compatible_checks(
                [item for item in value if item["name"] in names or item["status"] != "pass"], recorded)
        elif key == "progress_checks" and isinstance(value, dict) and isinstance(recorded, dict):
            actual[key] = {name: status for name, status in value.items()
                           if name in recorded or status != "pass"}
        else:
            actual[key] = compatible_checks(value, recorded)
    return actual


def compatible_state(actual: dict, expected: dict) -> dict:
    actual = actual.copy()
    for key in ("check_inputs", "fix_rounds", "fix_limit_hits"):
        if key not in expected:
            actual.pop(key, None)
    return compatible_checks(actual, expected)


def segment(path: Path, rows: list[dict], *, rerecord: Path | None = None) -> None:
    tick = import_module("lokay.tick")
    pi = import_module("lokay.effects.pi")
    gh = import_module("lokay.effects.gh")
    decide = import_module("lokay.effects.decide")
    manifest = json.loads(path.with_suffix(".json").read_text())
    entry = manifest.get("entry", "act")
    if entry not in ("act", "check"):
        raise ValueError("unsupported replay entry")

    class Boundary(BaseException):
        pass

    identities = {(row.get("tick"), row.get("repo"), row.get("issue")) for row in rows}
    sequences = [row["seq"] for row in rows]
    if (len(identities) != 1 or not rows or sequences != sorted(set(sequences))
            or rows[0].get("repo") != manifest["repo"]["name"]
            or rows[0].get("issue") != manifest["issue"]):
        raise ValueError("expected one tick/repo/issue with increasing unique seq")
    effects = [row for row in rows if row["kind"] == "call"]
    transitions = [row for row in rows if row["kind"] == "transition"]
    if not effects or not transitions:
        raise ValueError("tick segment needs calls and transitions")
    for row in rows:
        for key in ("effect", "before", "event", "after"):
            if key in row:
                row[key] = unpack(row[key], path.parent, source=path.parent)
    with TemporaryDirectory(prefix="lokay-replay-") as temporary, ExitStack() as stack:
        sandbox = Path(temporary).resolve()
        mappings = {old: str((sandbox / new).resolve()) for old, new in manifest["paths"].items()}
        if any(not Path(new).is_relative_to(sandbox) for new in mappings.values()):
            raise ValueError("fixture path escapes sandbox")

        def relocate(value, reverse=False) -> Any:
            if isinstance(value, str):
                pairs = {new: old for old, new in mappings.items()} if reverse else mappings
                for old, new in sorted(pairs.items(), key=lambda pair: -len(pair[0])):
                    value = value.replace(old, new)
                return value
            if isinstance(value, list):
                return [relocate(item, reverse) for item in value]
            if isinstance(value, dict):
                return {key: relocate(item, reverse) for key, item in value.items()}
            return value

        rows = relocate(rows)
        effects = [row for row in rows if row["kind"] == "call"]
        transitions = [row for row in rows if row["kind"] == "transition"]
        if entry == "check" and (
                transitions[0]["before"].get("node") != "check"
                or transitions[-1]["event"].get("action") != "verdict"
                or transitions[-1]["event"]["outcome"].get("result") not in ("fix", "merge")):
            raise ValueError("check segment must start at Check and end at a fix or merge verdict")
        recorded = []
        position = 0
        transition_position = 0
        requests = []
        request_seq = None

        def blocked(*args, **kwargs):
            raise Mismatch(f"seq={effects[position]['seq'] if position < len(effects) else 'end'} unrecorded external operation")

        def readonly(row):
            if row.get("call") != "git":
                return False
            argv = row.get("effect", {}).get("argv", [])
            args = argv[1:]
            index = next((i for i, arg in enumerate(args) if not arg.startswith("-")), None)
            if index is None:
                return False
            command = args[index]
            return command in {"show", "diff", "ls-files", "rev-parse", "cat-file", "merge-base",
                               "log", "status", "symbolic-ref", "check-ref-format", "for-each-ref"} or (
                command == "worktree" and args[index + 1:index + 2] == ["list"])

        def skip_readonly(limit):
            nonlocal position
            while position < len(effects) and effects[position]["seq"] < limit and readonly(effects[position]):
                position += 1

        def consume(kind, value):
            nonlocal position
            while True:
                row = effects[position] if position < len(effects) else {}
                effect = row.get("effect", {})
                expected = effect.get("input") if kind == "decide" else effect.get("argv")
                actual = value
                if (kind == "gh" and isinstance(expected, list) and value[1:3] == expected[1:3]
                        and value[1:3] in (["pr", "comment"], ["pr", "edit"])
                        and "--body" in value and "--body" in expected):
                    index = value.index("--body") + 1
                    if index == expected.index("--body") + 1:
                        actual = value.copy()
                        actual[index] = expected[index] if rerecord is not None else compatible_checks(value[index], expected[index])
                if rerecord is None and row and transition_position < len(transitions) and transitions[transition_position]["seq"] < row["seq"]:
                    raise Mismatch(f"seq={row['seq']} expected transition before call")
                if row.get("call") == kind and expected == actual:
                    position += 1
                    if rerecord is not None:
                        updated = deepcopy(row)
                        if kind != "decide":
                            updated["effect"]["argv"] = value
                            raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
                            updated["input"] = "sha256:" + hashlib.sha256(raw).hexdigest()
                        recorded.append(updated)
                    return effect
                if readonly(row):
                    position += 1
                    continue
                label = "request" if kind == "decide" else "argv"
                raise Mismatch(f"seq={row.get('seq', 'end')} expected {label}={expected!r}, got {label}={actual!r}")

        def process(argv, *, input=None, text=True, cwd=None, **kwargs):
            argv = list(argv)
            if argv and argv[0] == "curl" and requests:
                response = requests.pop(0)
                body = json.loads(argv[argv.index("-d") + 1])
                expected_body = deepcopy(response["body"])
                for wire in (body, expected_body):
                    for message in wire.get("messages", []):
                        if message.get("role") == "user":
                            message["content"] = json.loads(message["content"])
                if body != expected_body:
                    raise Mismatch(f"seq={request_seq} expected request={response['body']!r}, got request={body!r}")
                if "error" in response:
                    raise Mismatch(f"seq={request_seq} unsupported recorded decision exception")
                return CompletedProcess(argv, response["returncode"], response["stdout"], response["stderr"])
            command = pi.pi_command(argv)
            if command is not None:
                raise Mismatch("pi call contains nested guard effects; choose a segment without pi")
            kind = Path(argv[0]).name
            effect = consume(kind, argv)
            if effect["stdin"] != input:
                raise Mismatch(f"seq={effects[position - 1]['seq']} stdin mismatch")
            attempts = effect["attempts"]
            if len(attempts) != 1 or any("error" in attempt for attempt in attempts):
                raise Mismatch(f"seq={effects[position - 1]['seq']} unsupported recorded process exception")
            attempt = attempts[-1]
            stdout, stderr = attempt["stdout"], attempt["stderr"]
            if (kind == "git" and attempt["returncode"] == 0
                    and argv[1:] in (["rev-parse", "--show-toplevel"],
                                     ["rev-parse", "--git-common-dir"], ["rev-parse", "--git-dir"])):
                directory = (Path(cwd) / stdout.strip()).resolve()
                if not directory.is_relative_to(sandbox):
                    raise Mismatch("recorded git directory escapes sandbox")
                store.ensure_directory(directory)
            if not text:
                stdout, stderr = stdout.encode(), stderr.encode()
            return CompletedProcess(argv, attempt["returncode"], stdout, stderr)

        original_decision = decide._decide

        def decision(internal, recorder=None):
            nonlocal requests, request_seq
            effect = consume("decide", internal)
            requests = deepcopy(effect["requests"])
            request_seq = effects[position - 1]["seq"]
            result = original_decision(internal, recorder)
            if requests or result != effect["output"]:
                raise Mismatch(f"seq={request_seq} decision response mismatch")
            return result

        def logged(kind, **fields):
            nonlocal transition_position
            if kind != "transition":
                return
            fields = json.loads(json.dumps(fields, default=store.json_default))
            if rerecord is not None:
                recorded.append({**transitions[0], **fields, "kind": "transition"})
                if entry == "check" and fields["event"].get("action") == "verdict":
                    raise Boundary
                return
            if transition_position >= len(transitions):
                raise Mismatch("unrecorded transition")
            expected = transitions[transition_position]
            skip_readonly(expected["seq"])
            if position < len(effects) and effects[position]["seq"] < expected["seq"]:
                raise Mismatch(f"seq={effects[position]['seq']} expected call before transition")
            for key in ("before", "event", "after"):
                actual = fields[key]
                if key != "event":
                    actual = compatible_state(actual, expected[key])
                elif "fields" in actual and "fields" in expected[key]:
                    actual = {**actual, "fields": compatible_state(actual["fields"], expected[key]["fields"])}
                actual = compatible_checks(actual, expected[key])
                if stable(actual) != stable(expected[key]):
                    raise Mismatch(f"seq={expected['seq']} transition {key} mismatch: expected {stable(expected[key])!r}, got {stable(actual)!r}")
            transition_position += 1
            if (entry == "check" and transition_position == len(transitions)
                    and fields["event"].get("action") == "verdict"):
                raise Boundary

        home = sandbox / "home"
        store.ensure_directory(home)
        stack.enter_context(patch.dict(os.environ, {**manifest.get("env", {}), "HOME": str(home),
                                                   "LOKAY2_DECISION_API": manifest.get("api", "mini"),
                                                   "LOKAY2_DECISION_MODEL": manifest.get("model", ""),
                                                   "LOKAY2_DECISION_BASE_URL": "https://offline.invalid"}, clear=True))
        for module in (config, store, import_module("lokay.observe")):
            for name, value in (("HOME", home / ".lokay"), ("RUNS", home / ".lokay/runs"), ("LOCKS", home / ".lokay/locks")):
                if hasattr(module, name):
                    stack.enter_context(patch.object(module, name, value))
        original_process = pi.run_process
        for module in tuple(sys.modules.values()):
            if module and getattr(module, "__name__", "").startswith("lokay"):
                for name, value in tuple(vars(module).items()):
                    if value is original_process:
                        stack.enter_context(patch.object(module, name, process))
        stack.enter_context(patch.object(decide, "_decide", decision))
        stack.enter_context(patch.object(store, "log_event", logged))
        stack.enter_context(patch.object(tick, "repo_config", lambda name: relocate(manifest["repo"])))
        stack.enter_context(patch.object(gh, "gh_bin", lambda: relocate(manifest["gh"])))
        stack.enter_context(patch.object(pi, "_run_process", blocked))
        stack.enter_context(patch("subprocess.Popen", blocked))
        stack.enter_context(patch.object(socket, "socket", blocked))
        stack.enter_context(patch.object(pi, "retry_sleep", blocked))
        stack.enter_context(patch.object(tick.time, "time", lambda: manifest["time"]))
        files = dict(manifest.get("files", {}))
        if entry == "check":
            files[manifest["diff_path"]] = manifest["diff"]
        for target, source in files.items():
            destination = Path(relocate(target)).resolve()
            origin = (path.parent / source).resolve()
            if not destination.is_relative_to(sandbox) or not origin.is_relative_to(path.parent.resolve()):
                raise ValueError("fixture file escapes sandbox or fixture directory")
            store.write_artifact(destination, origin.read_text())
        before = relocate(manifest["before"])
        repo, issue = manifest["repo"]["name"], manifest["issue"]
        store.save_run(repo, issue, before)
        if before.get("node") == "check":
            stack.enter_context(patch("lokay.effects.tests.base_tests_on_head",
                                      lambda *args, **kwargs: {"result": "unknown", "tested": False}))
        if entry == "check":
            if not isinstance(manifest.get("uv"), str):
                raise ValueError("check manifest requires uv string")
            checks = import_module("lokay.checks")
            original_which = checks.shutil.which
            stack.enter_context(patch.object(checks.shutil, "which",
                                            lambda name, *args, **kwargs: manifest["uv"] if name == "uv"
                                            else original_which(name, *args, **kwargs)))
            configured = relocate(manifest["repo"])
            root, worktree = tick._repo_paths(configured, issue)
            git = import_module("lokay.effects.git")
            stack.enter_context(patch.object(git, "BASE_BRANCHES", {}))
            git.BASE_BRANCHES[(worktree.resolve(), None)] = manifest["base"]
            finish = import_module("lokay.finish")
            check = import_module("lokay.review")
            setup = import_module("lokay.setup")
            stack.enter_context(patch.object(setup, "prepare_dependencies",
                                            lambda *args, **kwargs: relocate(manifest["setup"])))
            picked = {**before, "repo": repo, "issue": issue}
            sha = before["sha"]
            branch = f"lokay/{issue}"
            tests = configured.get("test") or []
            base = manifest["base"]
            diff_path = Path(relocate(manifest["diff_path"])).resolve()
            if not diff_path.is_relative_to(sandbox):
                raise ValueError("fixture diff escapes sandbox")
            diff = diff_path.read_text()
            check_rows = check.hunks(diff)
            saved = store.state_read(repo, issue)
            try:
                ci = finish.local_checks(picked, worktree, configured, sha, root, base, tests, check_rows)
                pr_number, remote = finish.remote_checks(picked, branch, sha)
                if remote["result"] not in ("green", "no_ci", "inherited"):
                    raise Mismatch(f"unsupported check remote result: {remote['result']}")
                if remote.get("failed") and remote["result"] != "inherited":
                    raise Mismatch(f"unsupported check remote failures: {remote['failed']}")
                ci = {**ci, "ci": remote["result"],
                    **({"inherited": remote["inherited"]} if remote.get("inherited") else {}),
                    "failed": ci["failed"] + [
                        {"warstwa": "GitHub CI", "plik": "", "check": name,
                         "log": name + "\n" + (remote.get("failed_logs") or {}).get(name, name)}
                        for name in remote.get("failed") or []],
                    "notes": [*ci["notes"], *(remote.get("notes") or [])],
                    "result": "green" if ci["result"] == "green" and remote["result"] in ("green", "no_ci", "inherited") else "red"}
                store.state_update(repo, issue, local_ci=ci)
                rounds = before.get("check_rounds", 0)
                decisions, kinds, check_notes, dismissed_keys, plan_text, check_results, checks_failed, main_sha = finish.lenses(
                    picked, worktree, base, sha, saved, diff, check_rows, ci, rounds)
                verdict, rounds = finish.complete_check(
                    picked, worktree, base, sha, ci, decisions, plan_text, checks_failed, dismissed_keys,
                    check_results, pr_number, rounds, check_notes, hashlib.sha256(diff.encode()).hexdigest(),
                    kinds, conflict_fix=lambda files, log: finish.conflict_fix(picked, sha, files, log), main_sha=main_sha)
                store.state_update(repo, issue, _event={"action": "verdict", "outcome": verdict})
            except Boundary:
                outcome = (recorded[-1] if rerecord is not None else transitions[-1])["event"]["outcome"]
                detail = outcome
            else:
                raise Mismatch("check segment returned before final verdict boundary")
        else:
            if before.get("node") in ("plan", "build"):
                if not any(row.get("effect", {}).get("argv", [])[:4] == ["git", "worktree", "add", "--detach"]
                           or row.get("effect", {}).get("argv", [])[:4] == ["git", "checkout", "--detach", "--force"]
                           for row in effects):
                    stack.enter_context(patch("lokay.effects.git.plan_checkout", lambda root: root))
            event = tick.act(Run.from_state({**before, "repo": repo, "issue": issue}))
            outcome = event.outcome
            detail = event_record(event)
        after = store.load(repo, issue).state
        if rerecord is None and stable(compatible_state(after, transitions[-1]["after"])) != stable(transitions[-1]["after"]):
            raise Mismatch("final state mismatch")
        if rerecord is None and stable(compatible_checks(outcome, relocate(manifest["outcome"]))) != stable(relocate(manifest["outcome"])):
            raise Mismatch(f"final outcome mismatch: {detail!r}")
        skip_readonly(float("inf"))
        if position != len(effects) or (rerecord is None and transition_position != len(transitions)):
            raise Mismatch(f"unconsumed calls={len(effects) - position} transitions={len(transitions) - transition_position}")
        if rerecord is not None:
            store.write_segment(rerecord, path.parent, {**manifest, "outcome": relocate(outcome, True)},
                                relocate(recorded, True))
