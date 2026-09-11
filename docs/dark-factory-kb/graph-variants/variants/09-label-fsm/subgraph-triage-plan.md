# Subgraph: triage-plan

**Theme:** scout/triage + plan slot — agent wypełnia treść; approve to label HITL/policy.  
**Mode mix:** DET claim/flip; AGENT SO plan (opc. scout lane).

## Flow

```mermaid
flowchart TD
  A([enter: stage queued / planning]) --> B[DET: claim issue K=1 + lock]
  B --> C{claim ok?}
  C -->|occupied / defer| Z0([leave: defer])
  C -->|ok| D[DET: label → workflow:planning]
  D --> E[AGENT SO: scout lane build|plan]
  E --> F{lane?}
  F -->|build small| G[DET: skip plan slot → advance implementing]
  F -->|plan needed| H[AGENT SO: write plan comment schema]
  H --> I{SO ok?}
  I -->|ok:false| J[DET: label → needs-human / needs-info]
  J --> Z1([leave: escape])
  I -->|ok| K[DET: wait for workflow:plan-approved]
  K --> L{approved?}
  L -->|timeout / reject| J
  L -->|yes| M([leave: advance implementing])
  G --> M

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,D,G,K,J det
  class E,H agent
  class Z0,Z1 bad
```

## Notes

- **Slot ≠ router.** Scout SO zwraca `{lane: build|plan, …}`. DET mapuje lane na krawędź tabeli — agent nie woła kolejnego joba.
- **Plan comment = artefakt.** Schema: Outcome / Steps / Files / Risks / Ask-or-stop. Pin albo oznaczony komentarz (chippingway pinned JSON spirit).
- **HITL label.** `workflow:plan-approved` (jnurre `agent:plan-approved`) dokłada człowiek albo wąska policy DET — nie ten sam model, który pisał plan.
- **Small-build fast path.** gp-foundry scout→builder bez plannera gdy issue mały; tu to DET po enum `lane=build`.
- **Fail closed.** Brak planu / `ok:false` → `needs-human`, nie ciche „spróbuj innego modelu”.
- **Handoff:** `{issue_id, lane, plan_ref?}` → label-spine advance.
