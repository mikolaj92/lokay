# Subgraph: agent-leaf

**Theme:** Coding agent **za** agent adapterem — Claude Code / Codex / Kimi / OpenCode jako pluggable leaves.  
**Mode mix:** AGENT leaf only. FSM decyduje *kiedy*; adapter+silnik wypełnia SO.

## Flow

```mermaid
flowchart TD
  A([enter: agent seat scheduled]) --> B[DET: load agent adapter + engine id]
  B --> C[DET: inject ticket_ctx + schema + sandbox_ref]
  C --> D[DET: enforce timeout / token / tool budget]
  D --> E{leaf kind?}
  E -->|plan| P[AGENT SO: plan files / tests / stop_if]
  E -->|implement| I[AGENT: edit in sandbox via engine]
  E -->|bounded_fix| X[AGENT: fix from test/review fail]
  E -->|independent_review| R[AGENT other engine: critical verdict]
  P --> F{ok structured?}
  I --> F
  X --> F
  R --> F
  F -->|ok:true| OK[DET: persist artifact_ref via adapter]
  F -->|ok:false| NO[DET: write fail reason enum]
  OK --> OUT([leave: resume temporal-spine])
  NO --> OUT
  D -->|budget hard stop| KILL[DET: cancel leaf = fail]
  KILL --> OUT

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,C,D,OK,NO,KILL det
  class P,I,X,R agent
```

## Notes

- **Leaf, not brain.** Model nie wybiera następnego stanu FSM, nie przestawia board columns, nie woła merge, nie jest control plane.
- **Pluggable engines.** Ten sam seat: Claude Code / Codex / Kimi / OpenCode — wybór w manifeście / adapter config, nie w prompcie „zostań orkiestratorem”.
- **Executor ≠ Reviewer.** `independent_review` = **inny** engine id (albo co najmniej osobna sesja adaptera). Implement i review nie dzielą jednego kontekstu „sam siebie pochwal”.
- **Structured output.** `ok:true` + artefakt (plan.json / diff receipt / verdict) albo `ok:false` + reason enum. Brak limbo chat.
- **Meat ≡ AI.** Ten sam schema seat; kto wypełni SO nie zmienia krawędzi FSM.
- **Handoff contract.** Leave = `{state_id, engine, ok, artifact_ref, reason?, usage}` → Event/run history; spine idzie DET ścieżką.
