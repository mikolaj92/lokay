# Subgraph: llm-implement-review

**Theme:** LLM **tylko** w Activities Implement i Review — wypełnia SO; nie routuje Workflow; Plan nie jest agent leaf.  
**Mode mix:** AGENT leaf ×2. Workflow decyduje *kiedy*; Activity *jak* w budżecie.

## Flow

```mermaid
flowchart TD
  A([enter: LLM Activity scheduled]) --> B[DET: load schema + ticket_ctx + plan_ref]
  B --> C[DET: enforce timeout / token / tool budget]
  C --> D{seat?}
  D -->|Implement| I[AGENT SO: edit worktree from DET plan]
  D -->|Review| R[AGENT SO: critical PR verdict]
  D -->|other| FORBIDDEN[DET: reject — no Plan/router LLM]
  I --> E{ok structured?}
  R --> E
  E -->|ok:true| OK[DET: write Activity result + artifacts]
  E -->|ok:false| NO[DET: write fail reason enum]
  OK --> OUT([leave: resume Workflow])
  NO --> OUT
  C -->|budget hard stop| KILL[DET: fail Activity]
  KILL --> OUT
  FORBIDDEN --> OUT

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#a05050,color:#ffe8e8
  class B,C,OK,NO,KILL det
  class I,R agent
  class FORBIDDEN bad
```

## Notes

- **Narrower than 15.** Brak plan / generic llm-activity. Tylko Implement + Review.
- **Not a router.** Model nie wybiera następnego Activity, nie woła Signal, nie decyduje merge.
- **Repair = Implement again.** Po `runTests` fail Workflow planuje **kolejne** wywołanie Implement z `failure_log` — bounded N; nie „agent napraw świat”.
- **Reviewer ≠ implementer.** Osobna Activity, osobny prompt/schema — nawet gdy ten sam vendor modelu.
- **Meat ≡ AI.** Ten sam schema seat.
- **Handoff.** Leave = `{seat, ok, artifact_ref, reason?, usage}`.
