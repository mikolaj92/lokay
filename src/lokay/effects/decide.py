from __future__ import annotations

from json import dumps

import json
import math
import os
import subprocess
import sys
import time
from collections.abc import Mapping
from typing import Any, cast

EPS = 1e-5


class DecisionError(RuntimeError):
    pass


def _check(internal: Mapping, response: Mapping) -> dict:
    out: dict = {}
    for question in internal["questions"]:
        qid = question["id"]
        answer = response.get(qid)
        if not isinstance(answer, dict):
            raise DecisionError(f"missing {qid}")
        options = list(question["options"])
        probs = answer.get("probabilities") or {}
        if set(probs) != set(options):
            raise DecisionError(f"options {qid}")
        total = sum(float(v) for v in probs.values())
        if abs(total - 1) > EPS:
            raise DecisionError(f"sum {qid}")
        choice = answer.get("choice")
        if choice not in options:
            raise DecisionError(f"choice {qid}")
        top = max(options, key=lambda name: float(probs[name]))
        if choice != top:
            raise DecisionError(f"argmax {qid}")
        out[qid] = {
            "choice": choice,
            "probabilities": {name: round(float(probs[name]), 6) for name in options},
            "confidence": float(cast(Any, answer.get("confidence"))),
        }
        if "reason" in answer:
            out[qid]["reason"] = answer["reason"]
    return out


def _trim_wire(wire: dict, limit: int = 6000, string_limit: int = 3000) -> dict:
    strings = []

    def trim(value):
        if isinstance(value, str):
            return value[:string_limit]
        if isinstance(value, Mapping):
            value = {key: trim(item) for key, item in value.items()}
        elif isinstance(value, list):
            value = [trim(item) for item in value]
        else:
            return value
        for key, item in (value.items() if isinstance(value, dict) else enumerate(value)):
            if isinstance(item, str):
                strings.append((value, key))
        return value

    field = "state" if "state" in wire else "input"
    wire[field] = trim(wire[field])
    while (size := len(dumps(wire))) >= limit:
        available = [(parent, key) for parent, key in strings if parent[key]]
        if not available:
            wire[field] = {}
            strings = []
            if len(dumps(wire)) < limit:
                break
            questions = wire["questions"]
            items = list(questions.values()) if isinstance(questions, dict) else questions
            available = [(item, "question" if "question" in item else "instructions")
                         for item in items if item.get("question", item.get("instructions"))]
            if not available:
                raise DecisionError("request metadata exceeds character limit")
            size = len(dumps(wire))
        parent, key = max(available, key=lambda item: len(item[0][item[1]]))
        parent[key] = parent[key][:max(0, len(parent[key]) - max(1, (size - limit + 1) // 6))]
    return wire


def to_wire(api: str, model: str, internal: Mapping) -> dict:
    if api == "chat":
        questions = [{key: question[key] for key in ("id", "instructions", "options")}
                     for question in internal["questions"]]
        user = _trim_wire({"state": internal.get("state") or {}, "questions": questions},
                          limit=60000, string_limit=60000)
        properties = {}
        for question in internal["questions"]:
            options = list(question["options"])
            properties[question["id"]] = {
                "type": "object",
                "properties": {
                    "probabilities": {"type": "object",
                                      "properties": {option: {"type": "number"} for option in options},
                                      "required": options, "additionalProperties": False},
                    "choice": {"type": "string", "enum": options},
                    "reason": {"type": "string"},
                },
                "required": ["probabilities", "choice", "reason"], "additionalProperties": False,
            }
        return {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a careful code reviewer. Answer each question "
                 "independently based on the given state, including diff hunks. Give a probability "
                 "distribution over the allowed options for each question. Be specific per question; "
                 "do not give the same answer to every question by default. "
                 "state.history lists earlier findings on this PR and how they were addressed. "
                 "Do not re-raise a finding that was resolved or rejected in a dispute unless the current "
                 "diff reintroduces it; raise a new concern only if it is concrete and give its exact reason."},
                {"role": "user", "content": dumps(user)},
            ],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "decisions", "strict": True,
                "schema": {"type": "object", "properties": properties,
                           "required": list(properties), "additionalProperties": False},
            }},
        }
    if api == "tensorfold":
        questions = [{
            "id": question["id"],
            "type": "choice",
            "question": question["instructions"],
            "options": [{"name": k, "description": v} for k, v in question["options"].items()],
        } for question in internal["questions"]]
        return _trim_wire({
            "model": model,
            "input": internal.get("state") or {},
            "questions": questions,
            "chat_template_kwargs": {"enable_thinking": False},
            "prompt_format_version": 1,
        })
    if api == "mini":
        questions = {}
        for question in internal["questions"]:
            kind = "noul" if question["type"] == "bool" else question["type"]
            item = {"type": kind, "instructions": question["instructions"]}
            if kind != "noul":
                item["criteria"] = question["options"]
            questions[question["id"]] = item
        wire = {"state": internal.get("state") or {}, "questions": questions}
        return _trim_wire(wire)
    raise DecisionError(f"unknown api {api}")


def from_wire(api: str, model: str, payload: Mapping, internal: Mapping) -> dict:
    if api not in ("mini", "chat") and payload.get("model") not in (None, model):
        raise DecisionError("model mismatch")
    mapped = {}
    if api == "chat":
        try:
            content = payload["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            answers = json.loads(content)
            for question in internal["questions"]:
                qid = question["id"]
                raw = answers[qid]["probabilities"]
                if set(raw) != set(question["options"]):
                    raise DecisionError(f"options {qid}")
                probs = {option: float(raw[option]) for option in question["options"]}
                if not all(math.isfinite(p) for p in probs.values()):
                    raise DecisionError(f"probabilities {qid}")
                probs = {option: max(0.0, p) for option, p in probs.items()}
                total = sum(probs.values())
                if not math.isfinite(total):
                    raise DecisionError(f"sum {qid}")
                probs = {option: p / total if total else 1 / len(probs) for option, p in probs.items()}
                choice = max(probs, key=lambda option: probs[option])
                mapped[qid] = {"probabilities": probs, "choice": choice, "confidence": probs[choice]}
                if "reason" in answers[qid]:
                    reason = answers[qid]["reason"]
                    if not isinstance(reason, str):
                        raise DecisionError(f"reason {qid}")
                    mapped[qid]["reason"] = reason.strip()[:1500]
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
            raise DecisionError("invalid chat decision response") from exc
    elif api == "mini":
        mapped = {
            qid: {"choice": answer.get("label"), "probabilities": answer.get("probabilities"),
                  "confidence": answer.get("confidence")}
            for qid, answer in payload.items()
        }
    elif api == "tensorfold":
        usage = payload.get("usage") or {}
        if int(usage.get("completion_tokens") or 0) > 0:
            raise DecisionError("completion tokens")
        for qid, answer in (payload.get("answers") or {}).items():
            probs = answer["probabilities"]
            choice = answer["choice"]
            if choice not in probs:
                raise DecisionError(f"choice {qid}")
            mapped[qid] = {"choice": choice, "probabilities": probs, "confidence": float(probs[choice])}
    else:
        raise DecisionError(f"unknown api {api}")
    return _check(internal, mapped)


def decide(internal: Mapping) -> dict:
    from lokay.store import log_event

    started = time.monotonic()
    output = None
    ok = False
    responses = []
    try:
        output = _decide(internal, responses)
        ok = True
        return output
    except BaseException as exc:
        output = {"error": type(exc).__name__, "reason": str(exc)}
        raise
    finally:
        log_event("call", call="decide", name=",".join(str(q.get("id", "")) for q in internal.get("questions", []) if isinstance(q, Mapping))[:200],
                  input=internal, output=output, started=started, ok=ok,
                  effect={"input": internal, "requests": responses, "output": output})


def _decide(internal: Mapping, recorder: list | None = None) -> dict:
    from lokay.effects.pi import run_process
    from lokay.effects.retry import retry

    api = os.environ.get("LOKAY2_DECISION_API") or "mini"
    model = "" if api == "mini" else os.environ.get("LOKAY2_DECISION_MODEL") or os.environ["LOKAY2_MODEL"]
    base = os.environ["LOKAY2_DECISION_BASE_URL"].rstrip("/")
    path = {"mini": "/v1/decisions", "tensorfold": "/v1/decisions", "chat": "/chat/completions"}[api]
    body = dumps(to_wire(api, model, internal))
    timeout = str(int(float(os.environ.get("LOKAY2_DECISION_TIMEOUT") or (180 if api == "chat" else 30))))
    cmd = [
        "curl", "-sS", "-m", timeout,
        "-w", "\n%{http_code}",
        "-H", "content-type: application/json",
        "-d", body,
    ]
    key = os.environ.get("LOKAY2_DECISION_API_KEY")
    if key:
        cmd.extend(["-H", "@-"])
    cmd.append(base + path)
    size = len(body.encode("utf-8"))
    print(f"decide: request bytes={size} approx_tokens={size // 3}", file=sys.stderr)
    def transient(proc):
        if isinstance(proc, subprocess.TimeoutExpired):
            return "decision request timed out"
        if isinstance(proc, Exception):
            return None
        if proc.returncode != 0:
            return (proc.stderr.strip() or "curl failed") if proc.returncode in (52, 56, 28) else None
        status = proc.stdout.rpartition("\n")[2].strip()
        if status in ("408", "429") or (len(status) == 3 and status.isdecimal() and 500 <= int(status) <= 599):
            return f"http {status}"
        return None

    def request():
        response = {}
        try:
            try:
                proc = run_process(cmd, timeout=float(timeout) + 2,
                                   input=f"authorization: Bearer {key}\n" if key else None)
                response.update(stdout=proc.stdout, stderr=proc.stderr, returncode=proc.returncode)
                return proc
            except BaseException as exc:
                try:
                    response.update(error=type(exc).__name__,
                                    reason=f"request timed out after {exc.timeout} seconds" if isinstance(exc, subprocess.TimeoutExpired) else str(exc),
                                    stdout=getattr(exc, "stdout", None), stderr=getattr(exc, "stderr", None),
                                    returncode=getattr(exc, "returncode", None))
                except Exception:
                    pass
                raise
        except OSError:
            raise DecisionError("decision request failed or timed out") from None
        finally:
            if recorder is not None:
                try:
                    from lokay.store import redact

                    recorder.append(redact({"body": json.loads(body), **response}))
                except Exception:
                    pass

    try:
        proc = retry(request, 4, transient, call="decide")
    except subprocess.TimeoutExpired:
        raise DecisionError("decision request failed or timed out") from None
    if proc.returncode != 0:
        raise DecisionError(proc.stderr.strip() or "curl failed")
    raw, _, status = proc.stdout.rpartition("\n")
    status = status.strip()
    if status != "200":
        raise DecisionError(f"http {status}")
    return from_wire(api, model, json.loads(raw), internal)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--probe":
        internal = {
            "state": {},
            "questions": [
                {"id": "up", "type": "bool", "instructions": "up?", "options": {"true": "yes", "false": "no"}}
            ],
        }
    else:
        internal = json.load(sys.stdin)
    try:
        print(dumps(decide(internal), separators=(",", ":")))
    except Exception as exc:
        print(f"decide: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
