"""Owner command parsing. Not wired into the tick yet."""
import re

_COMMAND = re.compile(r"(?m)^/lokay (build|skip|retry)\b")


def owner_command(text):
    found = _COMMAND.findall(text or "")
    return found[-1] if found else None
