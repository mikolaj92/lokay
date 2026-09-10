# Anthropic Claude Code Action + Routines (GitHub surface)

**Typ:** open GitHub Action wrapper + closed model/runtime; Routines = Anthropic-hosted schedule  
**Powiązane:** [anthropic-claude-code.md](./anthropic-claude-code.md) (loop engineering / dynamic workflows)

## Architektura

```
GitHub event (issue/PR/comment) | schedule | repository_dispatch | Routines API
    → claude-code-action (na runnerze Actions LUB Anthropic Routines cloud)
    → Claude Code agentic loop (+ skills/MCP wg repo)
    → commit / PR / structured Action outputs
    → człowiek: review/merge (chyba że org auto-merge)
```

### Tryby
- **Interactive:** `@claude` na issue/PR — tracking comments
- **Automation mode:** input `prompt` → od razu agent, mniej spam comment
- **Routines (research preview ~2026-04):** schedule / GitHub event / API na infrastrukturze Anthropic (cloud autopilot)

## Human gates
- Permissions Action (contents, PRs)
- Branch protection
- Auto mode / tool approvals zależne od konfiguracji Claude Code w CI

## Eval / CI
- Sam Action **jest** w CI; może uruchamiać testy w jobie.
- Structured outputs → kolejne joby pipeline.

## Multi-agent / failure
- Pojedynczy Claude Code run per trigger (dynamic workflows możliwe jeśli włączone w środowisku Action).
- Retry = re-run workflow / bounded retry w orkiestratorze zewnętrznym.

## Open-source vs closed
Action repo **OSS** (anthropics/claude-code-action); model + Claude Code product closed.

## URL-e
- https://github.com/anthropics/claude-code-action
- https://github.com/anthropics/claude-code-action/blob/main/docs/custom-automations.md
- https://claude.com/blog/getting-started-with-loops
