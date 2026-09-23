# Subgraph: tester-baseline

**Theme:** **Tester** + `TEST_COMMAND` + porównanie z **baseline**; profile `auto` / `python` / `frontend` / `generic`.  
**Mode mix:** DET gate majority + AGENT leaf (Tester / Failure Analyst hint).

## Flow

```mermaid
flowchart TD
  A([enter: from planner-coder — commits on branch]) --> B[DET: resolve TEST_COMMAND + profile]
  B --> C[DET: run baseline snapshot if missing]
  C --> D[AGENT: Tester — interpret / focus SO optional]
  D --> E[DET: execute TEST_COMMAND in worktree]
  E --> F{exit 0 + baseline match / improve?}
  F -->|yes| G([leave: handoff pr-revise OK])
  F -->|no| H[DET: capture logs + diff vs baseline]
  H --> I{AUTO_REVISE budget left?}
  I -->|yes| J[AGENT: FailureAnalyst — hint SO]
  J --> K([leave: fail → ai:failed then ai:revise])
  I -->|no| L([leave: fail → ai:failed terminal])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef ag fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,C,E,H,I det
  class D,J ag
  class G ok
  class K,L bad
```

## Notes

- **Gate is DET.** Exit code + baseline comparison decydują — nie „Tester powiedział OK w prozie”.
- **Profiles.** `auto` wykrywa stack; `python` / `frontend` / `generic` mapują na typowe komendy (env `TEST_COMMAND` wygrywa).
- **Bounded revise.** `AUTO_REVISE_*` = budget; wyczerpanie → `ai:failed` bez kolejnego `ai:revise` (circuit breaker).
- **Failure Analyst = leaf.** Hint do kolejnego Planner/Coder; nie flipuje labels.
- **Handoff contract.** `{ok: true, test_log}` albo `{ok: false, evidence, revise: bool}`.
