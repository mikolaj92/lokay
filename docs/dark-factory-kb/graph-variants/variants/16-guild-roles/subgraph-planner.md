# Subgraph: planner

**Theme:** Guild Planner — issue → implementation plan; scoping quality dominates reliability.  
**Mode mix:** AGENT structured output; DET only for workspace/context fetch.

## Flow

```mermaid
flowchart TD
  A([enter: one job]) --> B[DET: fetch ticket + repo context]
  B --> C[AGENT SO: plan_issue]
  C --> D{ok?}
  D -->|false underspecified/too_large/dangerous| E[DET: skip clean — no limbo]
  E --> S([leave: skip])
  D -->|true| F[DET: persist plan artifact]
  F --> G[DET: derive branch name / sandbox prep signal]
  G --> H([leave: plan ready for Implementer])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,E,F,G det
  class C agent
```

## Structured output (plan_issue)

```json
{
  "ok": true,
  "goal": "...",
  "files": ["..."],
  "test_command": "...",
  "non_goals": ["..."],
  "stop_if": ["auth", "migration"]
}
```

lub `{ "ok": false, "reason": "underspecified"|"too_large"|"dangerous" }` → skip bez limbo.

## Notes

- **Narrow seat.** Planner only plans — does not write product code or open PRs.
- **Scoping is the reliability lever.** Guild lesson: plan quality >> model bravado at implement time.
- **stop_if is sacred.** Auth, migrations, secrets paths → skip or escalate to human; Implementer must not “wing it.”
- **Handoff contract.** Output = `{ticket, plan, branch_hint, test_command}` for Implementer.
- **Polish:** planista rozpisuje pliki/testy/non-goals; nie klepie kodu.
