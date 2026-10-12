from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping

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
            "confidence": float(answer.get("confidence")),
        }
    return out


def _trim_wire(wire: dict) -> dict:
    strings = []

    def trim(value):
        if isinstance(value, str):
            return value[:3000]
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
    while (size := len(json.dumps(wire))) >= 6000:
        if not strings:
            raise DecisionError("request metadata exceeds character limit")
        parent, key = max(strings, key=lambda item: len(item[0][item[1]]))
        if not parent[key]:
            raise DecisionError("request metadata exceeds character limit")
        parent[key] = parent[key][:max(0, len(parent[key]) - (size - 5999))]
    return wire


def to_wire(api: str, model: str, internal: Mapping) -> dict:
    if api == "tensorfold":
        questions = []
        for question in internal["questions"]:
            questions.append(
                {
                    "id": question["id"],
                    "type": "choice",
                    "question": question["instructions"],
                    "options": [{"name": k, "description": v} for k, v in question["options"].items()],
                }
            )
        return _trim_wire({
            "model": model,
            "input": internal.get("state") or {},
            "questions": questions,
            "chat_template_kwargs": {"enable_thinking": False},
            "prompt_format_version": 1,
        })
    if api == "openai-decisions":
        questions = []
        for question in internal["questions"]:
            kind = {"choice": "choice", "bool": "predicate", "score": "score"}[question["type"]]
            item = {"type": kind, "name": question["id"], "instructions": question["instructions"]}
            if kind == "score":
                item["levels"] = [{"label": k} for k in question["options"]]
            else:
                item["choices"] = [{"value": k, "description": v} for k, v in question["options"].items()]
            questions.append(item)
        return _trim_wire({"model": model, "input": internal.get("state") or {}, "questions": questions})
    if api in ("mini", "systemone"):
        questions = {}
        for question in internal["questions"]:
            kind = "noul" if question["type"] == "bool" else question["type"]
            item = {"type": kind, "instructions": question["instructions"]}
            if api != "mini" or kind != "noul":
                item["criteria"] = question["options"]
            questions[question["id"]] = item
        wire = {"state": internal.get("state") or {}, "questions": questions}
        if api != "mini":
            wire["model"] = model
        return _trim_wire(wire)
    raise DecisionError(f"unknown api {api}")


def from_wire(api: str, model: str, payload: Mapping, internal: Mapping) -> dict:
    if api != "mini" and payload.get("model") not in (None, model):
        raise DecisionError("model mismatch")
    if api == "mini":
        mapped = {
            qid: {"choice": answer.get("label"), "probabilities": answer.get("probabilities"),
                  "confidence": answer.get("confidence")}
            for qid, answer in payload.items()
        }
        return _check(internal, mapped)
    if api == "tensorfold":
        usage = payload.get("usage") or {}
        if int(usage.get("completion_tokens") or 0) > 0:
            raise DecisionError("completion tokens")
        mapped = {}
        for qid, answer in (payload.get("answers") or {}).items():
            probs = answer["probabilities"]
            choice = answer["choice"]
            if choice not in probs:
                raise DecisionError(f"choice {qid}")
            mapped[qid] = {"choice": choice, "probabilities": probs, "confidence": float(probs[choice])}
        return _check(internal, mapped)
    if api == "openai-decisions":
        mapped = {}
        for answer in payload.get("answers") or []:
            probs = {row["value"]: row["probability"] for row in answer.get("probabilities") or []}
            choice = answer["choice"]
            if answer.get("type") == "predicate":
                p = float(answer.get("probability", probs.get("true", 0)))
                probs = {"true": p, "false": 1 - p}
                choice = "true" if p >= 0.5 else "false"
            mapped[answer["name"]] = {"choice": choice, "probabilities": probs, "confidence": answer.get("confidence")}
        return _check(internal, mapped)
    if api == "systemone":
        mapped = {}
        for qid, answer in (payload.get("answers") or {}).items():
            probs = dict(answer.get("probabilities") or {})
            choice = answer["choice"]
            if "noul" in probs:
                noul = float(probs["noul"])
                probs = {"true": 1 - noul, "false": noul}
                choice = "false" if choice == "noul" else "true"
            mapped[qid] = {"choice": choice, "probabilities": probs, "confidence": answer.get("confidence")}
        return _check(internal, mapped)
    raise DecisionError(f"unknown api {api}")


def decide(internal: Mapping) -> dict:
    api = os.environ.get("LOKAY2_DECISION_API") or "mini"
    model = "" if api == "mini" else os.environ.get("LOKAY2_DECISION_MODEL") or os.environ["LOKAY2_MODEL"]
    base = os.environ["LOKAY2_DECISION_BASE_URL"].rstrip("/")
    path = {"mini": "/v1/decisions", "tensorfold": "/v1/decisions", "openai-decisions": "/decisions", "systemone": "/systemone"}[api]
    body = json.dumps(to_wire(api, model, internal))
    timeout = str(int(float(os.environ.get("LOKAY2_DECISION_TIMEOUT") or 30)))
    cmd = [
        "curl", "-sS", "-m", timeout,
        "-w", "\n%{http_code}",
        "-H", "content-type: application/json",
        "-d", body,
    ]
    key = os.environ.get("LOKAY2_DECISION_API_KEY")
    if key:
        cmd.extend(["-H", f"authorization: Bearer {key}"])
    cmd.append(base + path)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=float(timeout) + 2)
    except (OSError, subprocess.TimeoutExpired):
        raise DecisionError("decision request failed or timed out") from None
    if proc.returncode != 0:
        raise DecisionError(proc.stderr.strip() or "curl failed")
    raw, _, status = proc.stdout.rpartition("\n")
    if status.strip() != "200":
        raise DecisionError(f"http {status.strip()}")
    return from_wire(api, model, json.loads(raw), internal)


def main() -> int:
    import sys

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
        print(json.dumps(decide(internal), separators=(",", ":")))
    except Exception as exc:
        print(f"decide: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
