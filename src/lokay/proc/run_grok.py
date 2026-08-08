"""Explicit harness-named entry: same process as lokay-run-agent.

Not a silent fallback — both names are first-class scripts (docs/UNIX.md).
Harness selection is still config/env (`executor.agent` / LOKAY_AGENT).
"""

from lokay.proc.run_agent import main

if __name__ == "__main__":
    raise SystemExit(main())
