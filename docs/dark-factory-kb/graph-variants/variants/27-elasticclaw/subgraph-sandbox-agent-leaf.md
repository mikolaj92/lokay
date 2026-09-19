# Subgraph: sandbox-agent-leaf

**Theme:** OpenClaw w ephemeral sandbox — **jedyny** slot AGENT; liść, nie control plane.  
**Mode mix:** AGENT leaf only. Hub decyduje *kiedy*; sesja wypełnia pracę / SO.

## Flow

```mermaid
flowchart TD
  A([enter: stage inject scheduled]) --> B[DET: provision provider Daytona/CMX/exe.dev]
  B --> C[DET: mint scoped GitHub App installation token]
  C --> D[DET: bootstrap workspace + CONTEXT + Bridge]
  D --> E[DET: enforce timeout / tool / token budget]
  E --> F{leaf kind?}
  F -->|plan artifact| P[AGENT: write plan.json + PLAN_READY]
  F -->|implement| I[AGENT OpenClaw: edit in sandbox]
  F -->|bounded_fix| X[AGENT: fix from gate/judge fail]
  F -->|judge optional| J[AGENT judge: bounded inputs → verdict]
  P --> G{ok / signal?}
  I --> G
  X --> G
  J --> G
  G -->|ok| OK[DET: persist artifact_ref + outputs]
  G -->|fail / budget| NO[DET: mark run fail + sanitized comment]
  OK --> OUT([leave: resume hub-det-stages])
  NO --> OUT
  E -->|hard stop| KILL[DET: tear partial + ok false]
  KILL --> OUT

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,C,D,E,OK,NO,KILL det
  class P,I,X,J agent
```

## Notes

- **Leaf, not brain.** OpenClaw nie ewaluuje `pr_conditions`, nie wybiera `terminal`, nie woła cleanup Servera, nie przestawia cudzych stage’y.
- **Sandbox isolation.** Provider = Daytona / Replicated CMX / exe.dev. Bridge łączy sesję z ElasticClaw Server; host control plane zostaje poza VM.
- **Scoped creds.** GitHub App → tymczasowy installation token per agent — nie szeroki PAT / user OAuth na zawsze.
- **Meat ≡ AI.** Ten sam seat `inject`+sandbox; silnik nie rozróżnia kto wypełnił artefakt.
- **Judge ≠ router.** Opcjonalny `judge` to bounded review leaf; przejście po `judge_verdict` i tak robi hub.
- **Handoff contract.** Leave = `{stage_id, ok, artifact_ref, pr_url?, reason?, usage}` → outputs dla następnego hub trigger.
