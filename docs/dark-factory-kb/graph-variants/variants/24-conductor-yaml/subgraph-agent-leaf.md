# Subgraph: agent-leaf

**Theme:** `type: agent` — **jedyny** slot LLM; liść z izolowaną sesją; nie router.  
**Mode mix:** AGENT leaf only. Jinja/YAML decydują *kiedy*; sesja wypełnia SO.

## Flow

```mermaid
flowchart TD
  A([enter: type agent scheduled]) --> B[DET: load agent_spec + schema + ticket_ctx]
  B --> C[DET: enforce timeout / token / tool budget]
  C --> D{leaf kind?}
  D -->|plan| P[AGENT SO: plan files / tests / stop_if]
  D -->|implement| I[AGENT SO: edit in worktree]
  D -->|review| R[AGENT SO: critical review verdict]
  D -->|bounded_fix| F[AGENT SO: fix from failure_log]
  P --> E{ok structured?}
  I --> E
  R --> E
  F --> E
  E -->|ok:true| OK[DET: set vars + artifact_ref]
  E -->|ok:false| NO[DET: set fail reason enum]
  OK --> OUT([leave: resume jinja-routes])
  NO --> OUT
  C -->|budget hard stop| KILL[DET: fail leaf = set ok false]
  KILL --> OUT

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,C,OK,NO,KILL det
  class P,I,R,F agent
```

## Notes

- **Leaf, not brain.** Model nie ewaluuje Jinja, nie wybiera `terminate`, nie przestawia label FSM, nie merge’uje.
- **Isolated sessions.** Plan / implement / review / fix = osobne kroki `type: agent` (osobne sesje Conductor). Reviewer ≠ implementer nawet przy tym samym vendorze.
- **Structured output.** `ok:true` + artefakt albo `ok:false` + reason enum → `set` do vars → z powrotem do jinja-routes.
- **Meat ≡ AI.** Ten sam `type: agent` seat; silnik nie rozróżnia kto wypełnił SO.
- **Handoff contract.** Leave = `{step_id, ok, artifact_ref, reason?, usage}` → vars dla następnego first-match.
