# Subgraph: stage-spine

**Theme:** stała maszyna stanów `plan → approve → build → review → fix → ship` w Pythonie.  
**Mode mix:** **100% DET** w ciele spine. LLM tylko gdy spine **yield** do role leaf.

## Flow

```mermaid
flowchart TD
  A([enter: claimed issue / request]) --> B[DET: preflight — auth, disk, spend, locks]
  B --> C{preflight ok?}
  C -->|fail| X([leave: hold / skip — named reason])
  C -->|ok| D[DET: stage = plan]
  D --> E([yield: plan-approve])
  E --> F{approved?}
  F -->|no| X
  F -->|yes| G[DET: stage = build]
  G --> H([yield: build-review-fix])
  H --> I{review ok?}
  I -->|fix loop| H
  I -->|ok| J[DET: stage = ship]
  J --> K([yield: ship-merge-gate])
  K --> L([leave: shipped / merged / blocked receipt])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class B,D,G,J det
  class X,L stop
```

## Notes

- **Spine owns next stage.** Żaden liść LLM nie robi `stage = …`. Advance = kod po structured handoff.
- **Preflight before spend.** Auth silnika, worktree lock, disk, spend limits — fail → named hold, nie „agent napraw świat”.
- **One ticket, one run.** Claim + occupancy K=1; brak batch theatre.
- **Fix is a stage, not a vibe.** Po `review=block` spine ustawia `fix` i wraca do review — nie skok do ship.
- **Handoff.** `{stage, ticket_id, worktree?, attempt, receipt}` → podgraf; powrót zawsze przez DET transition table.
- **NOT:** ReAct router, label-swap FSM (to jnurre/hue), DOT compile (gp-foundry).
