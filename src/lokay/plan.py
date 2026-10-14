from __future__ import annotations

import json
from pathlib import Path

from lokay.decide import DecisionError, from_wire
from lokay.pi_step import pi_step
from lokay.safety import untrusted_issue_block

SECTIONS = ("## Cel", "## Pliki", "## Testy", "## Poza zakresem")
CRITERIA = ("k_cel", "k_pliki", "k_testy", "k_zakres")
PERSPECTIVES = ("minimal", "risk", "gates")
PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


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
    artifact.unlink(missing_ok=True)
    payload = pi_step(prompt + f"\nWrite the plan only to {artifact}.\n", artifact, cwd=cwd, env=env)
    if payload["result"] == "done" and not valid_plan(artifact):
        return {"result": "failed", "artifact": ""}
    return payload


def plan_one(perspective: str, prompt: str, art: Path, *, phase: str = "write", on_written=None) -> dict:
    from lokay.decide import decide

    if perspective not in PERSPECTIVES:
        raise ValueError("unknown plan perspective")
    if phase == "write" or not valid_plan(art):
        prompt += "\n" + (PROMPTS / f"plan_perspective_{perspective}.md").read_text()
        written = plan_write(prompt, art)
        if written["result"] != "done":
            return written
        if not valid_plan(art):
            return {"result": "failed", "reason": "invalid plan"}
        if on_written is not None:
            on_written()
    from lokay.run import check_deadline

    check_deadline()
    result = verdict(decide(plan_questions(art.read_text())))
    if result["next"] not in ("ok", "revise"):
        raise RuntimeError(f"unknown plan verdict: {result['next']}")
    return {"result": "done", **result}


def validate_synthesis(data: object, accepted: set[str]) -> dict:
    def obj(value, fields):
        if not isinstance(value, dict) or not all(field in value for field in fields):
            raise ValueError("missing synthesis fields")
        return value

    def text(value):
        if not isinstance(value, str):
            raise ValueError("synthesis text must be a string")

    def sources(value):
        if not isinstance(value, list) or not value:
            raise ValueError("synthesis sources must be a nonempty array")
        if any(not isinstance(source, str) or source not in accepted for source in value):
            raise ValueError("synthesis source was not accepted")

    data = obj(data, ("cel", "kryteria", "kroki", "pliki", "testy", "poza_zakresem", "odrzucone"))
    text(data["cel"])
    for field in ("kryteria", "kroki", "pliki", "testy", "poza_zakresem", "odrzucone"):
        if not isinstance(data[field], list):
            raise ValueError(f"{field} must be an array")
        for row in data[field]:
            if field == "odrzucone":
                row = obj(row, ("tresc", "zrodlo", "powod"))
                text(row["tresc"])
                text(row["powod"])
                if row["zrodlo"] not in PERSPECTIVES:
                    raise ValueError("unknown rejected source")
            else:
                fields = ("sciezka", "zmiana") if field == "pliki" else ("tresc",)
                row = obj(row, (*fields, "zrodla"))
                for name in fields:
                    text(row[name])
                sources(row["zrodla"])
    # Also validate source arrays in any extra fields allowed by the schema.
    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "zrodla":
                    sources(child)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(data)
    return data


def render_synthesis(data: dict) -> str:
    def items(field):
        return "\n".join(f"- {row['tresc']} [źródła: {', '.join(row['zrodla'])}]" for row in data[field])

    files = "\n".join(f"- {row['sciezka']}: {row['zmiana']} [źródła: {', '.join(row['zrodla'])}]"
                      for row in data["pliki"])
    rejected = "\n".join(f"- {row['tresc']} [{row['zrodlo']}]: {row['powod']}" for row in data["odrzucone"])
    return (f"## Cel\n{data['cel']}\n\n### Kryteria\n{items('kryteria')}\n\n"
            f"### Kroki\n{items('kroki')}\n\n## Pliki\n{files}\n\n"
            f"## Testy\n{items('testy')}\n\n## Poza zakresem\n{items('poza_zakresem')}\n\n"
            f"### Odrzucone\n{rejected}\n")


def synthesize(paths: dict[str, Path], issue: str, art: Path) -> dict:
    artifact = art.parent / "synthesis.json"
    prompt = (PROMPTS / "plan_synthesis.md").read_text() + "\n" + issue
    for perspective, path in paths.items():
        if perspective not in PERSPECTIVES:
            raise ValueError("unknown synthesis input")
        prompt += f"\n\nAccepted branch: {perspective}\n{path.read_text()}"
    prompt += f"\nWrite JSON only to {artifact}. Do not write plan.md.\n"
    artifact.unlink(missing_ok=True)
    payload = pi_step(prompt, artifact)
    if payload["result"] != "done":
        return payload
    try:
        data = validate_synthesis(json.loads(artifact.read_text()), set(paths))
    except (ValueError, OSError) as exc:
        return {"result": "failed", "reason": f"invalid synthesis: {exc}"}
    art.write_text(render_synthesis(data))
    return {"result": "done", "artifact": str(art)}


def plan_check(wire: dict, model: str, api: str = "tensorfold") -> dict:
    internal = plan_questions()
    try:
        answers = from_wire(api, model, wire, internal)
    except DecisionError:
        raise
    return verdict(answers)


def verdict(answers: dict) -> dict:
    confidence = answers["next"]["confidence"]
    uwagi = []
    notes = []
    for name in CRITERIA:
        p = answers[name]["probabilities"]["true"]
        if p < 0.35:
            uwagi.append({"kryterium": name, "p": p})
        elif p < 0.5:
            notes.append({"kryterium": name, "p": p})
    return {"next": "revise" if uwagi else "ok", "confidence": confidence, "uwagi": uwagi, "notes": notes}


def prompt_for(title: str, body: str | None) -> str:
    return Path(__file__).resolve().parents[2].joinpath("prompts/plan_write.md").read_text() + "\n" + untrusted_issue_block(title, body)
