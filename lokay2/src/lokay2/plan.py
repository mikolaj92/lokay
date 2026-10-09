from __future__ import annotations

import json
from pathlib import Path

from lokay2.decide import DecisionError, from_wire
from lokay2.pi_step import pi_step
from lokay2.safety import untrusted_issue_block

SECTIONS = ("## Cel", "## Pliki", "## Testy", "## Poza zakresem")
CRITERIA = ("k_cel", "k_pliki", "k_testy", "k_zakres")
THRESHOLD = 0.85


def plan_questions(plan: str = "") -> dict:
    return {
        "state": {"plan": plan},
        "questions": [
            {
                "id": "next",
                "type": "choice",
                "instructions": "Is the plan complete?",
                "options": {"ok": "ship it", "revise": "fix the plan"},
            },
            *[
                {
                    "id": name,
                    "type": "bool",
                    "instructions": text,
                    "options": {"true": "yes", "false": "no"},
                }
                for name, text in {
                    "k_cel": "Does Cel name the outcome?",
                    "k_pliki": "Does Pliki name the files to change?",
                    "k_testy": "Does Testy name a check that can fail?",
                    "k_zakres": "Does Poza zakresem name what stays out?",
                }.items()
            ],
        ],
    }


def valid_plan(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    text = path.read_text()
    return all(section in text for section in SECTIONS)


def plan_write(prompt: str, artifact: Path, *, cwd: Path | None = None, env: dict | None = None) -> dict:
    payload = pi_step(prompt + f"\nWrite the plan only to {artifact}.\n", artifact, cwd=cwd, env=env)
    if payload["result"] == "done" and not valid_plan(artifact):
        return {"result": "failed", "artifact": ""}
    return payload


def plan_check(wire: dict, model: str, api: str = "tensorfold") -> dict:
    internal = plan_questions()
    try:
        answers = from_wire(api, model, wire, internal)
    except DecisionError:
        raise
    return verdict(answers)


def verdict(answers: dict) -> dict:
    choice = answers["next"]["choice"]
    confidence = answers["next"]["confidence"]
    uwagi = []
    for name in CRITERIA:
        p = answers[name]["probabilities"]["true"]
        if p < THRESHOLD:
            uwagi.append({"kryterium": name, "p": p})
    ok = choice == "ok" and confidence >= THRESHOLD and not uwagi
    return {"next": "ok" if ok else "revise", "confidence": confidence, "uwagi": uwagi}


def prompt_for(title: str, body: str | None) -> str:
    return Path(__file__).resolve().parents[2].joinpath("prompts/plan_write.md").read_text() + "\n" + untrusted_issue_block(title, body)
