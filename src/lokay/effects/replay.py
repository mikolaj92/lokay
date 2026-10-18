from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack
from copy import deepcopy
from importlib import import_module
import os
from pathlib import Path
import socket
from subprocess import CompletedProcess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
from typing import Any

from lokay import config, store
from lokay.replay import unpack
from lokay.types import Run, event_record


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


def compatible_state(actual: dict, expected: dict) -> dict:
    actual = actual.copy()
    if "check_inputs" not in expected:
        actual.pop("check_inputs", None)
    return actual


def segment(path: Path, rows: list[dict]) -> None:
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

        def relocate(value) -> Any:
            if isinstance(value, str):
                for old, new in sorted(mappings.items(), key=lambda pair: -len(pair[0])):
                    value = value.replace(old, new)
                return value
            if isinstance(value, list):
                return [relocate(item) for item in value]
            if isinstance(value, dict):
                return {key: relocate(item) for key, item in value.items()}
            return value

        rows = relocate(rows)
        effects = [row for row in rows if row["kind"] == "call"]
        transitions = [row for row in rows if row["kind"] == "transition"]
        if entry == "check" and (
                transitions[0]["before"].get("node") != "check"
                or transitions[-1]["event"].get("action") != "verdict"
                or transitions[-1]["event"]["outcome"].get("result") not in ("fix", "merge")):
            raise ValueError("check segment must start at Check and end at a fix or merge verdict")
        position = 0
        transition_position = 0
        requests = []
        request_seq = None

        def blocked(*args, **kwargs):
            raise Mismatch(f"seq={effects[position]['seq'] if position < len(effects) else 'end'} unrecorded external operation")

        def consume(kind, value):
            nonlocal position
            row = effects[position] if position < len(effects) else {}
            effect = row.get("effect", {})
            expected = effect.get("input") if kind == "decide" else effect.get("argv")
            if row.get("call") != kind or expected != value:
                label = "request" if kind == "decide" else "argv"
                raise Mismatch(f"seq={row.get('seq', 'end')} expected {label}={expected!r}, got {label}={value!r}")
            if transition_position < len(transitions) and transitions[transition_position]["seq"] < row["seq"]:
                raise Mismatch(f"seq={row['seq']} expected transition before call")
            position += 1
            return effect

        def process(argv, *, input=None, text=True, cwd=None, **kwargs):
            argv = list(argv)
            if argv and argv[0] == "curl" and requests:
                response = requests.pop(0)
                body = json.loads(argv[argv.index("-d") + 1])
                if body != response["body"]:
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
            if transition_position >= len(transitions):
                raise Mismatch("unrecorded transition")
            expected = transitions[transition_position]
            if position < len(effects) and effects[position]["seq"] < expected["seq"]:
                raise Mismatch(f"seq={effects[position]['seq']} expected call before transition")
            for key in ("before", "event", "after"):
                actual = fields[key]
                if key != "event":
                    actual = compatible_state(actual, expected[key])
                elif "fields" in actual and "fields" in expected[key]:
                    actual = {**actual, "fields": compatible_state(actual["fields"], expected[key]["fields"])}
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
                if remote["result"] not in ("green", "no_ci"):
                    raise Mismatch(f"unsupported check remote result: {remote['result']}")
                if remote.get("failed"):
                    raise Mismatch(f"unsupported check remote failures: {remote['failed']}")
                ci = {**ci, "ci": remote["result"], "notes": [*ci["notes"], *(remote.get("notes") or [])],
                    "result": "green" if ci["result"] == "green" and remote["result"] in ("green", "no_ci") else "red"}
                store.state_update(repo, issue, local_ci=ci)
                rounds = before.get("check_rounds", 0)
                decisions, kinds, check_notes, dismissed_keys, plan_text, check_results, checks_failed = finish.lenses(
                    picked, worktree, base, sha, saved, diff, check_rows, ci, rounds)
                verdict, rounds = finish.complete_check(
                    picked, worktree, base, sha, ci, decisions, plan_text, checks_failed, dismissed_keys,
                    check_results, pr_number, rounds, check_notes, hashlib.sha256(diff.encode()).hexdigest(),
                    kinds, conflict_fix=lambda files, log: finish.conflict_fix(picked, sha, files, log))
                store.state_update(repo, issue, _event={"action": "verdict", "outcome": verdict})
            except Boundary:
                outcome = transitions[-1]["event"]["outcome"]
                detail = outcome
            else:
                raise Mismatch("check segment returned before final verdict boundary")
        else:
            event = tick.act(Run.from_state({**before, "repo": repo, "issue": issue}))
            outcome = event.outcome
            detail = event_record(event)
        after = store.load(repo, issue).state
        if stable(compatible_state(after, transitions[-1]["after"])) != stable(transitions[-1]["after"]):
            raise Mismatch("final state mismatch")
        if stable(outcome) != stable(relocate(manifest["outcome"])):
            raise Mismatch(f"final outcome mismatch: {detail!r}")
        if position != len(effects) or transition_position != len(transitions):
            raise Mismatch(f"unconsumed calls={len(effects) - position} transitions={len(transitions) - transition_position}")
