# Subgraph: prove-review-merge

**Theme:** `box prove` przed kasą → your tests → independent reviewer → merge policy.  
**Mode mix:** DET gates + yield AGENT leaves. Fail closed / vacuous-green refused.

## Flow

```mermaid
flowchart TD
  A([enter: gate phase]) --> B{gate?}
  B -->|box_prove| P[DET: setup + validate in real sandbox]
  P --> C{prove ok?}
  C -->|fail| HOLD([leave: hold named finding — no agent spend])
  C -->|ok| REC[DET: record gate → resume spine]
  B -->|run_tests| T[DET: CI adapter / your suite]
  T --> D{declared tests?}
  D -->|none| VG[DET: vacuous-green HOLD]
  VG --> HOLD2([leave: hold — not pass])
  D -->|yes| E{green?}
  E -->|green| REC
  E -->|red| R{attempts left?}
  R -->|yes| FIX([yield: agent-leaf bounded_fix])
  R -->|exhausted| ESC([leave: escalate / skip])
  B -->|independent_review| REV([yield: agent-leaf other engine])
  REV --> F{verdict?}
  F -->|reject| FIX2([yield: agent-leaf bounded_fix])
  F -->|ok| REC
  B -->|merge_policy| M{Off / Classify / Always}
  M -->|Off| DRAFT[DET: PR draft for human]
  M -->|Classify| CL[DET: classify atom + policy]
  M -->|Always| MER[DET: merge under policy]
  DRAFT --> HITL([leave: human gate / done draft])
  CL --> HITL
  MER --> DONE([leave: done merged])
  FIX --> REC
  FIX2 --> REC

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class P,T,VG,DRAFT,CL,MER det
  class HOLD,HOLD2,ESC,HITL,DONE stop
```

## Notes

- **Prove before spend.** `box prove` fail = named finding, **zero** tokenów na implement. To wyróżnik openfactory-core wśród low-star mills.
- **Vacuous-green = hold.** Brak test command w projekcie nie jest zielonym CI — hold z powodem, nie silent pass.
- **Reviewer osobno.** Independent review always other engine leaf; reject wraca do bounded_fix, nie do „tego samego chatu”.
- **Coder ceiling = open PR.** Merge to polityka (Off default) + human na prod — nie agent klika merge.
- **Stall → human.** Blocked job dostaje executable options przez notifier; człowiek ewaluuje, nie „agent wymyśl lane”.
- **Handoff.** Leave hold/escalate/done = receipt w run state; yield agent-leaf = `{failure_log|pr_diff, attempt, engine, schema}`.
