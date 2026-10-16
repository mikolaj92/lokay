from __future__ import annotations

import json
import re
from pathlib import Path

from lokay import store

from lokay.effects.pi import pi_step
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
    store.remove_file(artifact)
    payload = pi_step(prompt + f"\nWrite the plan only to {artifact}.\n", artifact, cwd=cwd, env=env)
    if payload["result"] == "done" and not valid_plan(artifact):
        return {"result": "failed", "artifact": ""}
    return payload


def plan_one(perspective: str, prompt: str, art: Path, *, cwd: Path | None = None, phase: str = "write", on_written=None, single: bool = False, env: dict | None = None) -> dict:
    from lokay.effects.decide import decide

    if perspective not in PERSPECTIVES:
        raise ValueError("unknown plan perspective")
    if phase == "write" or not valid_plan(art):
        prompt += "\n" + (PROMPTS / f"plan_perspective_{perspective}.md").read_text()
        if single:
            prompt += (
                "\nWrite the final plan directly as Markdown in exactly this structure and order:\n"
                "## Cel\nOutcome text\n\n### Kryteria\n- Criterion [źródła: minimal]\n\n"
                "### Kroki\n- Step [źródła: minimal]\n\n## Pliki\n- path: change [źródła: minimal]\n\n"
                "## Testy\n- Check [źródła: minimal]\n\n## Poza zakresem\n- Exclusion [źródła: minimal]\n\n"
                "### Odrzucone\n- Rejected proposal [minimal]: reason\n"
                "Replace placeholders with concrete content; leave Odrzucone empty if nothing was rejected.\n"
            )
        prompt += "\nThe current directory is a read-only checkout of the repository at main, to be read but not modified.\n"
        written = plan_write(prompt, art, cwd=cwd, env=env)
        if written["result"] != "done":
            return written
        if not valid_plan(art):
            return {"result": "failed", "reason": "invalid plan"}
        if on_written is not None:
            on_written()
    from lokay.effects.pi import check_deadline

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

    change_field = "zmiana"
    files = "\n".join(f"- {row['sciezka']}: {row.get(change_field, '')} [źródła: {', '.join(row['zrodla'])}]"
                      for row in data["pliki"])
    rejected = "\n".join(f"- {row['tresc']} [{row['zrodlo']}]: {row['powod']}" for row in data["odrzucone"])
    return (f"## Cel\n{data['cel']}\n\n### Kryteria\n{items('kryteria')}\n\n"
            f"### Kroki\n{items('kroki')}\n\n## Pliki\n{files}\n\n"
            f"## Testy\n{items('testy')}\n\n## Poza zakresem\n{items('poza_zakresem')}\n\n"
            f"### Odrzucone\n{rejected}\n")


def synthesize(paths: dict[str, Path], issue: str, art: Path, *, cwd: Path | None = None, env: dict | None = None) -> dict:
    artifact = art.parent / "synthesis.json"
    prompt = (PROMPTS / "plan_synthesis.md").read_text() + "\n" + issue
    for perspective, path in paths.items():
        if perspective not in PERSPECTIVES:
            raise ValueError("unknown synthesis input")
        prompt += f"\n\nAccepted branch: {perspective}\n{path.read_text()}"
    prompt += f"\nWrite JSON only to {artifact}. Do not write plan.md.\n"
    store.remove_file(artifact)
    payload = pi_step(prompt, artifact, cwd=cwd, env=env)
    if payload["result"] != "done":
        return payload
    try:
        data = validate_synthesis(json.loads(artifact.read_text()), set(paths))
    except (ValueError, OSError) as exc:
        return {"result": "failed", "reason": f"invalid synthesis: {exc}"}
    store.write_artifact(art, render_synthesis(data))
    return {"result": "done", "artifact": str(art)}


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


def parent_criteria(body: str, accepted_plan: str = "") -> list[dict]:
    def extract(text, plan=False):
        rows = []
        active = False
        depth = 0
        for line in text.splitlines():
            heading = re.match(r"^(#{1,6})\s+(.+)", line)
            if heading:
                name = heading[2].strip().casefold()
                wanted = ("acceptance", "kryteria", "criteria")
                if any(word in name for word in wanted):
                    active, depth = True, len(heading[1])
                elif len(heading[1]) <= depth:
                    active = False
                continue
            checklist = re.match(r"^\s*[-*+]\s+\[[ xX]\]\s+(.+)", line)
            bullet = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.+)", line)
            value = checklist[1] if checklist and not plan else bullet[1] if active and bullet else None
            if value:
                value = re.sub(r"\s*\[źródła:.*?\]\s*$", "", value).strip()
                if len(value.split()) >= 3 and value not in rows:
                    rows.append(value)
        return rows

    rows = extract(body)
    if len(rows) < 2:
        rows = extract(accepted_plan, True)
    if len(rows) < 2:
        raise ValueError("decomposition requires at least two concrete parent acceptance criteria")
    return [{"id": f"c{index}", "text": text} for index, text in enumerate(rows, 1)]


def validate_decomposition(data: object, criteria: list[dict]) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list) or len(data["tasks"]) < 2:
        raise ValueError("decomposition requires at least two tasks")
    parent = {row["id"] for row in criteria}
    seen, covered = set(), set()
    for task in data["tasks"]:
        if not isinstance(task, dict):
            raise ValueError("invalid decomposition task")
        slug = task.get("id")
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or slug in seen:
            raise ValueError("task ids must be unique stable slugs")
        seen.add(slug)
        if any(not isinstance(task.get(key), str) or len(task[key].split()) < 3 for key in ("title", "body")):
            raise ValueError("tasks require concrete title and body")
        refs = task.get("criteria")
        if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
            raise ValueError("invalid criterion references")
        subset = set(refs)
        if len(subset) != len(refs) or not subset or not subset < parent or subset & covered:
            raise ValueError("task criteria must be disjoint nonempty proper subsets")
        covered |= subset
    if covered != parent:
        raise ValueError("tasks must cover all parent criteria")
    return {"criteria": criteria, "tasks": data["tasks"]}


def decompose(title: str, body: str, criteria: list[dict], artifact: Path, *, cwd: Path | None, env: dict) -> dict:
    prompt = ("Decompose this issue into smaller independently mergeable tasks. Do not modify the checkout. "
              "Write JSON with tasks: [{id: stable-lowercase-slug, title: concrete title, body: implementation scope, "
              "criteria: [parent criterion ids]}]. Use at least two tasks. Assign each parent criterion exactly once. "
              "Each task must cover a nonempty proper subset of the parent criteria.\n"
              + untrusted_issue_block(title, body) + "\nParent criteria:\n" + json.dumps(criteria)
              + f"\nWrite JSON only to {artifact}.")
    store.remove_file(artifact)
    outcome = pi_step(prompt, artifact, cwd=cwd, env=env)
    if outcome.get("result") != "done":
        raise RuntimeError("decomposition pi step failed")
    return validate_decomposition(json.loads(artifact.read_text()), criteria)


def prompt_for(title: str, body: str | None) -> str:
    return (PROMPTS / "plan_write.md").read_text() + "\n" + untrusted_issue_block(title, body)
