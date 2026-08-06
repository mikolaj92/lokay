"""Backward-compatible re-export. Prefer lokay.agent."""

from lokay.agent import build_grok_argv, run_agent as run_grok

__all__ = ["build_grok_argv", "run_grok"]
