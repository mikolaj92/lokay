from __future__ import annotations

import json
import os
import urllib.request
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
        return {
            "model": model,
            "input": internal.get("state") or {},
            "questions": questions,
            "chat_template_kwargs": {"enable_thinking": False},
            "prompt_format_version": 1,
        }
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
        return {"model": model, "input": internal.get("state") or {}, "questions": questions}
    if api == "systemone":
        questions = {}
        for question in internal["questions"]:
            kind = "noul" if question["type"] == "bool" else question["type"]
            questions[question["id"]] = {
                "type": kind,
                "instructions": question["instructions"],
                "criteria": question["options"],
            }
        return {"model": model, "state": internal.get("state") or {}, "questions": questions}
    raise DecisionError(f"unknown api {api}")


def from_wire(api: str, model: str, payload: Mapping, internal: Mapping) -> dict:
    if payload.get("model") not in (None, model):
        raise DecisionError("model mismatch")
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
    api = os.environ["LOKAY2_DECISION_API"]
    model = os.environ.get("LOKAY2_DECISION_MODEL") or os.environ["LOKAY2_MODEL"]
    base = os.environ["LOKAY2_DECISION_BASE_URL"].rstrip("/")
    path = {"tensorfold": "/v1/decisions", "openai-decisions": "/decisions", "systemone": "/systemone"}[api]
    body = json.dumps(to_wire(api, model, internal)).encode()
    headers = {"content-type": "application/json"}
    key = os.environ.get("LOKAY2_DECISION_API_KEY")
    if key:
        headers["authorization"] = f"Bearer {key}"
    request = urllib.request.Request(base + path, data=body, headers=headers)
    timeout = float(os.environ.get("LOKAY2_DECISION_TIMEOUT") or 30)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode()
        status = getattr(response, "status", 200)
    if status != 200:
        raise DecisionError(f"http {status}")
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
