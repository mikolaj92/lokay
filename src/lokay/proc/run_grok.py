"""Back-compat CLI name for lokay-run-agent (same atom).

Historical entrypoint. Prefer ``lokay-run-agent`` — harness is chosen only by
``executor.command`` / ``executor.args`` in config.
"""

from __future__ import annotations

from lokay.proc.run_agent import main

if __name__ == "__main__":
    raise SystemExit(main())
