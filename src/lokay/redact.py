from __future__ import annotations

import os
import re
from collections.abc import Mapping


def redact_text(text: str, env: Mapping[str, str] | None = None) -> str:
    secrets = sorted({value for source in (os.environ, env or {}) for key, value in source.items()
                      if value and re.search(r"TOKEN|SECRET|PASSWORD|API[_-]?KEY", key, re.IGNORECASE)},
                     key=lambda value: (-len(value), value))
    for secret in secrets:
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|xox[abposr]-[A-Za-z0-9-]+|sk-(?:proj-|ant-)?[A-Za-z0-9_-]+|AIza[A-Za-z0-9_-]{30,}|(?:AKIA|ASIA)[A-Z0-9]{16})\b",
                  "[REDACTED]", text)
    text = re.sub(r'''(?i)(--headers?(?:=|\s+)|-H\s+|\bhttp(?:\.[^\s=]+)?\.extraheader=)("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s"']+)''',
                  r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(\b(?:authorization|proxy-authorization|x-api-key|api-key|cookie|set-cookie)\s*[:=]\s*)[^\r\n]+",
                  r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(\b(?:bearer|basic)\s+)[A-Za-z0-9_./+=-]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(https?://)[^/\s@]+@", r"\1[REDACTED]@", text)
    text = re.sub(r'''(?i)(\b[A-Z0-9_-]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_-]*\s*[:=]\s*)(?!\s*\[REDACTED\])("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|"(?:\\[^\r\n]|[^"\\\r\n])*(?:\\)?(?=[\r\n]|$)|'(?:\\[^\r\n]|[^'\\\r\n])*(?:\\)?(?=[\r\n]|$)|[^\s,;"'\]}]+)''',
                  r"\1[REDACTED]", text)
    return text
