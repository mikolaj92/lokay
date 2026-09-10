# thegpvc/gp-foundry

**Confidence: 88** — klepacz + crew w GitHub Actions; graf DOT = deterministyczny kręgosłup.

## Co to jest

Kompiluje `harness.dot` → workflowy Actions. Scout→builder→reviewer→fixer→merge_gate. Stan w labels/PR/cron.

## Graf

```mermaid
flowchart TD
  open[issues.opened] --> scout[scout triage]
  scout -->|plan| planner[planner read-only]
  scout -->|build| builder[builder → PR]
  planner -->|build| builder
  builder --> reviewer[pr-review]
  reviewer -->|approve| gate[merge_gate]
  reviewer -->|changes| fixer[fixer max 3]
  fixer --> reviewer
  fixer -->|attempts>=3| human[needs-human]
  gate -->|ok| merge[auto-merge]
  gate -->|rebase| janitor[janitor rebase]
  cron[supervisor cron] --> stranded[re-drive / escalate]
```

## Co / gdzie / jak

| Element | Wartość |
|---------|---------|
| Trigger | GitHub events + labels |
| Executor | GitHub Actions (zero własnego daemona) |
| Agent | Claude Code OAuth + AGENT_PAT |
| Merge | Policy YAML, nie persona |
| Self-heal | janitor, supervisor, retro memory |

## Linki

- https://github.com/thegpvc/gp-foundry
