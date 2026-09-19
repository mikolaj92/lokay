# Subgraph: babysit

**Theme:** DET zabiera wyczerpujące klepanie — dirty tree, labelki, stuck PR, CI poll/retry.  
**Mode mix:** 100% DET. Człowiek nie babysittuje; agent nie „ratuje” infrastruktury.

## Flow

```mermaid
flowchart TD
  A([enter: cycle start]) --> B[DET: worktree clean?]
  B -->|dirty| X1([leave: hold — receipt dirty_worktree])
  B -->|clean| C[DET: re-check ready-for-agent / ai:ready]
  C -->|missing| X2([leave: skip — receipt missing_label])
  C -->|ok| D[DET: survey stuck PRs / open ai/*]
  D -->|stuck beyond bound| X3([leave: hold — receipt stuck_pr])
  D -->|lane clear| E[DET: fetch CI for open relevant PRs]
  E --> F{pending / red / green?}
  F -->|pending + budget| G[DET: sleep backoff + poll]
  G --> E
  F -->|pending exhausted| X4([leave: hold — receipt ci_timeout])
  F -->|red + flaky + budget| H[DET: re-run failed jobs]
  H --> E
  F -->|red hard / budget 0| X5([leave: hold — receipt ci_red])
  F -->|green / nothing open| I([leave: clean lane → ship])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,C,D,E,G,H det
  class X1,X2,X3,X4,X5 bad
```

## Notes

- **To jest sens human-amplify.** Energia inżyniera nie idzie w poll/retry/dirty — idzie w arch-gate i QA audit.
- **Bounds are sacred.** `poll_budget`, `rerun_budget`, `max_wall_clock`, `stuck_age`. Wyczerpanie → hold z receipt, nie limbo label.
- **Fail-closed front door.** Brudny worktree / brak labela / stuck PR = nie startujemy nowego shipa.
- **No AGENT here.** LLM nie interpretuje logów CI żeby „uznać za zielone”. CI jest wyrocznią.
- **Hard fail vs flaky.** Compile / typecheck / policy = hard. Allowlist flake = flaky. Nieznane = hard.
- **Handoff:** `{lane:clean}` albo `{hold:true, reason, receipt_id}` / `{skip:true, reason}`.
