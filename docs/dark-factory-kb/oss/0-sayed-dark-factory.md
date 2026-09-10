# 0-sayed/dark-factory

- Repo: https://github.com/0-sayed/dark-factory
- Składniki: Codex + Archon workflows + Agent Orchestrator + worktree-compose

## Teza

Planning folder opisuje *co budować*. Bootstrap PR (T000) z nadzorem człowieka, potem autonomia:
plan → implement (`auto-feature`) → review cleanup (`auto-squash`) → `merge-gate`.

## Mechanika

- Agent Orchestrator: workers, worktrees, procesy, logi
- worktree-compose: izolacja Docker Compose per worktree
- Archon: prompt → shell → prompt (step workflows)
- Concurrent tasks (np. 3) z Codex

## Gate ludzki

Świadomy bootstrap; potem dark. Escalation przez merge-gate / orchestrator, nie wieczne limbo intake.
