<!-- spine: spine_deterministic -->
# anthropics/claude-code-action

**Confidence: 92** — oficjalny label/automation → branch/PR; budulec klepacza w Actions.

## Co to jest

GitHub Action: interactive `@claude` albo automation `prompt` → edycja, commit, PR. Biega na Twoim runnerze.

## Graf

```mermaid
flowchart TD
  ev[Issue assign / label / comment / schedule] --> mode{prompt?}
  mode -->|nie| interact[Interactive @claude]
  mode -->|tak| auto[Automation agent mode]
  interact --> work[Checkout + Claude Code tools]
  auto --> work
  work --> out[Comment / commit / PR]
  out --> human[Człowiek review + merge]
```

## Co / gdzie / jak

| Element | Wartość |
|---------|---------|
| Trigger | issues, PR, comments, repository_dispatch, Routines |
| Sandbox | Runner + checkout |
| Merge | Domyślnie ludzki (branch protection) |
| Nie jest | Multi-repo daemon / L5 |

## Linki

- https://github.com/anthropics/claude-code-action
- https://github.com/anthropics/claude-code-action/blob/main/docs/custom-automations.md
