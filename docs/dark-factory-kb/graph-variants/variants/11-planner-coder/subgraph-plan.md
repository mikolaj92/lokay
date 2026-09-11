# Subgraph: plan

**Theme:** light agent #1 — **plan-only** structured output. Zero kodu, zero gita.  
**Mode mix:** DET context fetch; AGENT SO `plan_issue`.

## Flow

```mermaid
flowchart TD
  A([enter: ticket + branch_hint]) --> B[DET: fetch ticket + repo context]
  B --> C[AGENT SO: plan_issue]
  C --> D{ok?}
  D -->|false underspecified/too_large/dangerous| E[DET: skip clean — no limbo]
  E --> S([leave: skip])
  D -->|true| F[DET: persist plan artifact]
  F --> G{needs_breakdown?}
  G -->|true| H([leave: plan → task-breakdown])
  G -->|false| I([leave: plan ready → implement])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,E,F det
  class C agent
```

## Structured output (`plan_issue`)

```json
{
  "ok": true,
  "goal": "...",
  "files": ["..."],
  "test_command": "...",
  "non_goals": ["..."],
  "stop_if": ["auth", "migration"],
  "needs_breakdown": false
}
```

albo `{ "ok": false, "reason": "underspecified"|"too_large"|"dangerous" }` → skip bez limbo.

## Notes

- **Narrow seat.** Planista **tylko planuje** — nie pisze produktowego kodu, nie commit'uje, nie otwiera PR.
- **stop_if is sacred.** Auth, migrations, secrets → skip / escalate; implement nie „wing it”.
- **needs_breakdown** to flaga, nie obowiązek. Default = false → prosto do implement.
- **Scoping = dźwignia niezawodności.** Jakość planu > bravado modelu w coderze.
- **Handoff contract.** Output = `{ticket, plan, branch_hint, test_command, needs_breakdown}` .
- **Polish:** lekki agent #1 — rozpisuje jak zrobić issue; klepanie zostawia #2.
