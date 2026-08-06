"""Alias: lokay-run-grok → same as lokay-run-agent (harness name is not architecture)."""

from lokay.proc.run_agent import main

if __name__ == "__main__":
    raise SystemExit(main())
