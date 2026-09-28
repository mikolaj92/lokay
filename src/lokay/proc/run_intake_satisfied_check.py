from pathlib import Path

from lokay.intake import check_satisfied
from lokay.models import Issue
from lokay.proc._prose_agent import ask

_PROMPT = """Read the issue. Reply with one JSON object and nothing else:
{{"already_on_main": false, "remove_paths": ["relative/path"], "add_paths": ["relative/path"]}}
remove_paths are files the issue says to delete. add_paths are files it says to create.
already_on_main is true only when the issue states the work already landed.

Issue #{number} — {title}

{body}
"""


def run(issue: dict, clone: dict, *, execute=None) -> dict:
    item = Issue.from_dict(issue["issue"])
    prompt = _PROMPT.format(number=item.number, title=item.title or "", body=item.body or "")
    agent = ask(item, {**issue, **clone}, prompt, execute)
    return {
        "ok": True,
        "route": "selected",
        "check": check_satisfied(
            item,
            clone_path=Path(clone["clone_path"]) if clone.get("clone_path") else None,
            agent=agent,
        ).to_dict(),
    }
