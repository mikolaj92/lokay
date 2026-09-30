from lokay.intake import check_ambiguity
from lokay.models import Issue
from lokay.proc._prose_agent import ask

_PROMPT = """Read the issue. Reply with one JSON object and nothing else:
{{"verdict": "split"|"park"|"pass", "reason": "short_snake_case"}}
split when the issue is several pieces of work. park when it states no acceptance.
pass when one reader could implement it as written.

Issue #{number} — {title}

{body}
"""


def run(issue: dict, *, execute=None) -> dict:
    item = Issue.from_dict(issue["issue"])
    agent = _verdict(item, issue, execute)
    return {
        "ok": True,
        "route": "selected",
        "check": check_ambiguity(item, agent=agent).to_dict(),
    }


def _verdict(issue: Issue, raw: dict, execute) -> dict | None:
    prompt = _PROMPT.format(number=issue.number, title=issue.title or "", body=issue.body or "")
    return ask(issue, raw, prompt, execute)
