# peter-stratton/dark-factory (`godark`)

**Confidence: 90** — pełny mill issue→PR→merge z adversarial review; bliżej harness+klepacz niż L5 banku, ale ma escalate `needs-human-review`.

## Co to jest

Go CLI + Claude Code: milestone issues → implementer → quality reviewer → functional reviewer → squash-merge lub escalate. Harness = design.

## Graf

```mermaid
flowchart TD
  ms[Milestone issues p1-p3] --> dep{Deps open?}
  dep -->|tak| skip[Skip]
  dep -->|nie| impl[Implementer: kod + unit + PR]
  impl --> guard[Guard: Closes N, protected files]
  guard --> qr[Quality reviewer bez write]
  qr -->|changes| impl
  qr -->|ok| fr[Functional reviewer + ephemeral tests]
  fr -->|changes| impl
  fr -->|ok| merge[Squash-merge]
  fr -->|fail N| esc[needs-human-review]
  merge --> punch[Punchlist checkboxy]
```

## Co / gdzie / jak

| Element | Wartość |
|---------|---------|
| Trigger | Milestone + priority; deps w body |
| Sandbox | Docker ephemeral |
| Role | Implementer ≠ reviewers (izolacja uprawnień) |
| Merge | Auto squash lub escalate |
| Host | Laptop + Docker, nie flota |

## Linki

- https://github.com/peter-stratton/dark-factory
- https://godarkfactory.com
