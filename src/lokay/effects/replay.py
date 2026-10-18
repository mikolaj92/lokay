from __future__ import annotations

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


def segment(path: Path, rows: list[dict]) -> None:
    tick = import_module("lokay.tick")
    pi = import_module("lokay.effects.pi")
    gh = import_module("lokay.effects.gh")
    decide = import_module("lokay.effects.decide")
    manifest = json.loads(path.with_suffix(".json").read_text())
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
            if transition_position >= len(transitions):
                raise Mismatch("unrecorded transition")
            expected = transitions[transition_position]
            if position < len(effects) and effects[position]["seq"] < expected["seq"]:
                raise Mismatch(f"seq={effects[position]['seq']} expected call before transition")
            for key in ("before", "event", "after"):
                if stable(fields[key]) != stable(expected[key]):
                    raise Mismatch(f"seq={expected['seq']} transition {key} mismatch: expected {stable(expected[key])!r}, got {stable(fields[key])!r}")
            transition_position += 1

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
        for target, source in manifest.get("files", {}).items():
            destination = Path(relocate(target)).resolve()
            origin = (path.parent / source).resolve()
            if not destination.is_relative_to(sandbox) or not origin.is_relative_to(path.parent.resolve()):
                raise ValueError("fixture file escapes sandbox or fixture directory")
            store.write_artifact(destination, origin.read_text())
        before = relocate(manifest["before"])
        repo, issue = manifest["repo"]["name"], manifest["issue"]
        store.save_run(repo, issue, before)
        event = tick.act(Run.from_state({**before, "repo": repo, "issue": issue}))
        after = store.load(repo, issue).state
        if stable(after) != stable(transitions[-1]["after"]):
            raise Mismatch("final state mismatch")
        if stable(event.outcome) != stable(relocate(manifest["outcome"])):
            raise Mismatch(f"final outcome mismatch: {event_record(event)!r}")
        if position != len(effects) or transition_position != len(transitions):
            raise Mismatch(f"unconsumed calls={len(effects) - position} transitions={len(transitions) - transition_position}")
