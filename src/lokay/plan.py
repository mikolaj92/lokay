from __future__ import annotations

import json
import re
from pathlib import Path

from lokay import store

from lokay.effects.pi import pi_step
from lokay.safety import untrusted_issue_block
from lokay.scope import NEW_FILE_MARKER, kind as scope_kind, plan_file_lists, plan_required_path_errors, required_path_errors

SECTIONS = ("## Cel", "## Pliki", "## Testy", "## Poza zakresem")
CRITERIA = ("k_cel", "k_pliki", "k_testy", "k_zakres")
PERSPECTIVES = ("minimal", "risk", "gates")
DIFFICULTIES = ("easy", "medium", "hard", "too_big")
PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


def issue_kind(title: str | None) -> str | None:
    if title is not None:
        if title.startswith("[docs-audit]"):
            return "docs_change"
        if title.startswith(("[code-audit]", "[test-audit]")):
            return "code"
    return None


def plan_questions(plan: str = "", title: str | None = None, body: str | None = None) -> dict:
    return {
        "state": {"plan": plan, "issue": {"title": title, "body": body}},
        "questions": [
            {
                "id": "next",
                "type": "choice",
                "instructions": "Is the plan complete?",
                "options": {"ok": "ship it", "revise": "fix the plan"},
            },
            {
                "id": "kind",
                "type": "choice",
                "instructions": "What kind of change do the issue's done-criteria require? Judge the issue, not the plan.",
                "options": {
                    "code": "the issue changes code",
                    "docs_change": "the issue only touches docs (including 'add a missing description')",
                },
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
                    "k_pliki": "Does Pliki separate Wymagane (must modify, nowy=true only for created files, rendered with ' (nowy plik)') from Warunkowe (each with a condition)?",
                    "k_testy": "Does Testy name a check that can fail?",
                    "k_zakres": "Does Poza zakresem name what stays out?",
                }.items()
            ],
        ],
    }


def valid_plan_text(text: str, plan_schema: int | None = None) -> bool:
    return ((plan_schema != 2 or plan_file_lists(text) is not None)
            and all(section in text for section in SECTIONS)
            and not re.search(r"git\s+(?:commit|push|reset|rebase)\b|\bgh[ \t]+", text, re.IGNORECASE))


def base_paths(root: Path | None) -> set[str] | None:
    if root is None:
        return None
    from lokay.effects.git import base_branch, git_try

    code, out, err = git_try(root, "ls-tree", "-r", "--name-only", "-z", f"origin/{base_branch(root)}")
    if code:
        raise RuntimeError((err or out).strip())
    return set(out.split("\0")) - {""}


def valid_plan(path: Path, plan_schema: int | None = None, *, existing: set[str] | None = None) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    text = path.read_text()
    return (valid_plan_text(text, plan_schema)
            and (plan_schema != 2 or not plan_required_path_errors(text, existing)))


def path_verdict(path: Path, plan_schema: int | None, existing: set[str] | None = None) -> dict | None:
    bad = plan_required_path_errors(path.read_text(), existing) if plan_schema == 2 else []
    if bad:
        return {"next": "revise", "uwagi": [{"kryterium": "k_pliki", "paths": bad,
                "reason": "invalid required paths: " + ", ".join(bad)}]}
    return None


def plan_write(prompt: str, artifact: Path, *, cwd: Path | None = None, env: dict | None = None) -> dict:
    store.remove_file(artifact)
    payload = pi_step(prompt + f"\nWrite the plan only to {artifact}.\n", artifact, cwd=cwd, env=env)
    if payload["result"] == "done" and not valid_plan(artifact):
        return {"result": "failed", "artifact": ""}
    return payload


def plan_one(perspective: str, prompt: str, art: Path, *, cwd: Path | None = None, phase: str = "write", on_written=None, single: bool = False, plan_schema: int | None = None) -> dict:
    from lokay.effects.decide import decide

    if perspective not in PERSPECTIVES:
        raise ValueError("unknown plan perspective")
    if phase == "write" or not valid_plan(art, plan_schema):
        prompt += "\n" + (PROMPTS / f"plan_perspective_{perspective}.md").read_text()
        prompt += ("\n" + (PROMPTS / "plan_synthesis.md").read_text()
                   + f"\nWrite one {'final' if single else 'branch'} plan from perspective {perspective}. "
                   + f"Use only {perspective} in zrodla. No other branches exist.\n")
        prompt += "\nThe current directory is a read-only checkout of the repository at main, to be read but not modified.\n"
        written = write_synthesis(prompt, art, {perspective}, cwd=cwd)
        if written["result"] != "done":
            return written
        if not valid_plan(art, 2):
            return {"result": "failed", "reason": "invalid plan"}
        plan_schema = 2
        if on_written is not None:
            on_written()
    from lokay.effects.pi import check_deadline

    check_deadline()
    text = art.read_text()
    result = (path_verdict(art, plan_schema, base_paths(cwd) if plan_schema == 2 else None)
              or verdict(decide(plan_questions(text, None, None)), text))
    if result["next"] not in ("ok", "revise"):
        raise RuntimeError(f"unknown plan verdict: {result['next']}")
    return {"result": "done", **result}


def validate_synthesis(data: object, accepted: set[str], *, cwd: Path | None = None) -> dict:
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
    files = obj(data["pliki"], ("wymagane", "warunkowe"))
    for field in ("wymagane", "warunkowe"):
        if not isinstance(files[field], list):
            raise ValueError(f"{field} must be an array")
        for row in files[field]:
            fields = ("sciezka", "zmiana", "warunek") if field == "warunkowe" else ("sciezka", "zmiana")
            row = obj(row, (*fields, "zrodla"))
            for name in fields:
                text(row[name])
            if field == "warunkowe" and not row["warunek"].strip():
                raise ValueError("conditional file requires a condition")
            if field == "wymagane" and type(row.get("nowy")) is not bool:
                raise ValueError("required file requires boolean nowy")
            sources(row["zrodla"])
    bad = required_path_errors([(row["sciezka"], row["nowy"]) for row in files["wymagane"]],
                               base_paths(cwd) if files["wymagane"] else None)
    if bad:
        raise ValueError("invalid required paths: " + ", ".join(bad))
    for field in ("kryteria", "kroki", "testy", "poza_zakresem", "odrzucone"):
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
                fields = ("tresc",)
                row = obj(row, (*fields, "zrodla"))
                for name in fields:
                    text(row[name])
                sources(row["zrodla"])
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
    sections = []
    for field, title in (("wymagane", "Wymagane"), ("warunkowe", "Warunkowe")):
        rows = []
        for row in data["pliki"][field]:
            condition = f" — warunek: {row['warunek']}" if field == "warunkowe" else ""
            marker = NEW_FILE_MARKER if field == "wymagane" and row["nowy"] else ""
            rows.append(f"- {row['sciezka']}{marker}: {row[change_field]}{condition} [źródła: {', '.join(row['zrodla'])}]")
        sections.append(f"### {title}\n" + "\n".join(rows))
    files = "\n\n".join(sections)
    rejected = "\n".join(f"- {row['tresc']} [{row['zrodlo']}]: {row['powod']}" for row in data["odrzucone"])
    return (f"## Cel\n{data['cel']}\n\n### Kryteria\n{items('kryteria')}\n\n"
            f"### Kroki\n{items('kroki')}\n\n## Pliki\n{files}\n\n"
            f"## Testy\n{items('testy')}\n\n## Poza zakresem\n{items('poza_zakresem')}\n\n"
            f"### Odrzucone\n{rejected}\n")


def synthesize(paths: dict[str, Path], issue: str, art: Path, *, cwd: Path | None = None) -> dict:
    prompt = (PROMPTS / "plan_synthesis.md").read_text() + "\n" + issue
    for perspective, path in paths.items():
        if perspective not in PERSPECTIVES:
            raise ValueError("unknown synthesis input")
        prompt += f"\n\nAccepted branch: {perspective}\n{path.read_text()}"
    return write_synthesis(prompt, art, set(paths), cwd=cwd)


def write_synthesis(prompt: str, art: Path, accepted: set[str], *, cwd: Path | None = None) -> dict:
    artifact = art.with_suffix(".json")
    prompt += f"\nWrite JSON only to {artifact}. Do not write Markdown.\n"
    store.remove_file(artifact)
    payload = pi_step(prompt, artifact, cwd=cwd)
    if payload["result"] != "done":
        return payload
    try:
        data = validate_synthesis(json.loads(artifact.read_text()), accepted, cwd=cwd)
    except (ValueError, OSError) as exc:
        return {"result": "failed", "reason": f"invalid synthesis: {exc}"}
    text = render_synthesis(data)
    if not valid_plan_text(text, 2):
        return {"result": "failed", "reason": "invalid plan"}
    store.write_artifact(art, text)
    return {"result": "done", "artifact": str(art)}


def verdict(answers: dict, text: str = "", kind: str | None = None) -> dict:
    if kind is None:
        kind = answers["kind"]["choice"] if "kind" in answers else "code"
    if kind not in ("code", "docs_change"):
        raise ValueError("unknown issue kind")
    confidence = answers["next"]["confidence"]
    uwagi = []
    notes = []
    for name in CRITERIA:
        p = answers[name]["probabilities"]["true"]
        if p < 0.35:
            uwagi.append({"kryterium": name, "p": p})
        elif p < 0.5:
            notes.append({"kryterium": name, "p": p})
    files = plan_file_lists(text)
    if kind == "code" and files and files["Wymagane"] and scope_kind(sorted(files["Wymagane"])) == "docs":
        uwagi = [{"kryterium": "k_pliki", "reason": "docs-only plan for a code issue: Wymagane must include the code the done-criteria require"}]
    return {"next": "revise" if uwagi else "ok", "kind": kind,
            "confidence": confidence, "uwagi": uwagi, "notes": notes}


def difficulty_questions(title: str, body: str | None) -> dict:
    return {"state": {"title": title, "body": body or ""}, "questions": [{
        "id": "difficulty", "type": "choice",
        "instructions": "Rate implementation difficulty for one PR.",
        "options": dict(zip(DIFFICULTIES, ("one plan", "compare two plans",
                                          "synthesize three plans", "split into smaller tasks"))),
    }]}


def comparison_questions(paths: dict[str, Path], context: str) -> dict:
    return {"state": {"issue": context, "plans": {name: path.read_text() for name, path in paths.items()}},
            "questions": [{"id": "next", "type": "choice",
                           "instructions": "Choose the best accepted plan to implement.",
                           "options": {name: f"Implement the {name} plan" for name in paths}}]}


def validate_tasks(data: object) -> list[dict]:
    if not isinstance(data, list) or len(data) < 2:
        raise ValueError("split requires at least two tasks")
    for task in data:
        if not isinstance(task, dict) or any(
                not isinstance(task.get(key), str) or not task[key].strip() for key in ("title", "body")):
            raise ValueError("split task requires nonempty title and body")
    return [{"title": task["title"].strip(), "body": task["body"].strip()} for task in data]


def split_tasks(prompt: str, artifact: Path, *, cwd: Path | None = None) -> dict:
    store.remove_file(artifact)
    payload = pi_step(prompt + "\nList at least two smaller, independently mergeable tasks. "
                      "Write only a JSON array of objects with nonempty title and body to "
                      + str(artifact) + ". Do not create issues or modify repository files.", artifact, cwd=cwd)
    if payload["result"] != "done":
        return payload
    try:
        tasks = validate_tasks(json.loads(artifact.read_text()))
    except (ValueError, OSError) as exc:
        return {"result": "failed", "reason": f"invalid split: {exc}"}
    return {"result": "done", "tasks": tasks}


def prompt_for(title: str, body: str | None) -> str:
    return (PROMPTS / "plan_write.md").read_text() + "\n" + untrusted_issue_block(title, body)
