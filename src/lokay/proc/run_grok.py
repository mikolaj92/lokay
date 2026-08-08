"""Deprecated alias of ``lokay-run-agent``.

Kept so old scripts do not break. Prefer ``lokay-run-agent`` — the harness is
chosen only by ``executor.command`` / ``executor.args`` in config, not by this
entry point name.
"""

from __future__ import annotations

from lokay.proc.run_agent import main

if __name__ == "__main__":
    raise SystemExit(main())
