# ready-for-agent

**Confidence: 95** — najbliższy kanonowi KLEPACZ: zdejmuje babysitting issue→merged PR, nie L5.

## Co to jest

Lokalny harness (UI + CLI, npm) wokół GitHub/GitLab issues z etykietą `ready-for-agent`. Ty projektujesz; agent implementuje, reviewuje, otwiera PR i merguje według polityki.

## Graf

```mermaid
flowchart TD
  eng[Inżynier pisze issue] --> lab[Etykieta ready-for-agent]
  lab --> ui[Harness lista tylko labelowanych]
  ui --> wt[Fresh worktree + install]
  wt --> agent[Headless agent: implement]
  agent --> rev[Agent/model review]
  rev --> pr[Otwórz PR Closes N]
  pr --> pol{Merge Policy}
  pol -->|Off| human[Człowiek merguje]
  pol -->|Classify| risk[Decide PR Merge niskie ryzyko]
  pol -->|Always| auto[Merge gdy CI/no_checks OK]
  risk --> auto
```

## Co / gdzie / jak

| Element | Wartość |
|---------|---------|
| Trigger | Label `ready-for-agent` (domyślnie tylko Twoje autorstwo) |
| Sandbox | Fresh worktree per issue |
| Agent | Claude / Codex / OpenCode / Grok (konfigurowalne) |
| Testy | Build/install w worktree; CI na PR |
| Merge | Off / Classify / Always per repo |
| Nie robi | Backlog, wymyślanie ticketów, architektura produktu |

## Linki

- https://github.com/berenddeboer/ready-for-agent
- https://www.npmjs.com/package/ready-for-agent
- https://github.com/berenddeboer/ready-for-agent/blob/main/CONTEXT.md
