# Subgraph: task-breakdown (optional)

**Theme:** opcjonalny lekki AGENT SO — rozpisanie plików / tasków gdy plan lub ticket jest za gruby na jeden implement shot.  
**Mode mix:** AGENT SO; DET tylko persist. **Default path omija ten subgraph.**

## Flow

```mermaid
flowchart TD
  A([enter: plan with needs_breakdown]) --> B[AGENT SO: task_breakdown]
  B --> C{ok?}
  C -->|false still too_large| D[DET: skip clean / escalate]
  D --> S([leave: skip])
  C -->|true| E[DET: persist task list artifact]
  E --> F([leave: ordered tasks → implement])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class D,E det
  class B agent
```

## Structured output (`task_breakdown`)

```json
{
  "ok": true,
  "tasks": [
    {
      "id": "t1",
      "title": "...",
      "files": ["..."],
      "done_when": "..."
    }
  ]
}
```

albo `{ "ok": false, "reason": "still_too_large"|"ambiguous" }` → skip / escalate, nie half-plan limbo.

## Notes

- **Optional by design.** Dual-light-agents działa bez tego liścia; włącza się tylko gdy `needs_breakdown` albo operator.
- **Nie jest trzecim orkiestratorem.** Nie wybiera następnego stage'u grafu — tylko rozbija scope na listę tasków dla implement.
- **Nie pisze kodu.** Breakdown ≠ implement; coder nadal jest osobnym SO leaf.
- **Bounded list.** Mała, uporządkowana lista; nie epicki backlog w środku passu.
- **Handoff contract.** Output = `{plan, tasks[]}` dla subgraph-implement (implement idzie task po tasku lub jednym shotem według polityki).
- **Polish:** gdy trzeba — rozpisz pliki/taski; gdy nie trzeba — pomiń i klep od razu.
