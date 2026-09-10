# Anthropic Claude Code Action + Routines

- Action: https://github.com/anthropics/claude-code-action
- Custom automations: https://github.com/anthropics/claude-code-action/blob/main/docs/custom-automations.md
- Routines (cloud autopilot, research preview ~2026-04): schedule / GitHub event / API na infrastrukturze Anthropic

## Mechanika

- **Interactive**: `@claude` na issue/PR
- **Automation mode**: input `prompt` → od razu agent, bez tracking comment spam
- Trigger: issues, PR, comments, `repository_dispatch`, schedule (Routines)
- Biega na **Twoim** runnerze Actions (albo cloud Routines)
- Structured outputs → GitHub Action outputs

## Dark factory?

Budulec jak Copilot agent / godark worker: event → Claude Code → commit/PR.
Pełny mill = skleić z kolejką, merge gate, bounded retry (por. gp-foundry + Claude).
