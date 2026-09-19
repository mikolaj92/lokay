# Subgraph: llm-activity

**Theme:** LLM siedzi **wewnątrz** jednego Activity / `step.run` — wypełnia SO; nie routuje grafu.  
**Mode mix:** AGENT leaf only. Workflow decyduje *kiedy* ten step; Activity decyduje *jak* w budżecie.

## Flow

```mermaid
flowchart TD
  A([enter: LLM Activity scheduled]) --> B[DET: load prompt_ref + schema + ticket_ctx]
  B --> C[DET: enforce timeout / token / tool budget]
  C --> D{leaf kind?}
  D -->|plan_issue| P[AGENT SO: plan files / tests / stop_if]
  D -->|implement| I[AGENT SO: edit in worktree]
  D -->|pr_review| R[AGENT SO: critical review verdict]
  D -->|repair_from_tests| F[AGENT SO: bounded fix from failure_log]
  P --> E{ok structured?}
  I --> E
  R --> E
  F --> E
  E -->|ok:true| OK[DET: write Activity result + artifacts]
  E -->|ok:false| NO[DET: write fail reason enum]
  OK --> OUT([leave: resume Workflow])
  NO --> OUT
  C -->|budget hard stop| KILL[DET: cancel Activity = fail]
  KILL --> OUT

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,C,OK,NO,KILL det
  class P,I,R,F agent
```

## Notes

- **Not a router.** Model nie wybiera „co dalej”. Nie woła `StartWorkflow`, nie przestawia label FSM, nie decyduje o merge.
- **One step, one leaf.** Plan / implement / review / repair to osobne Activities (osobne memo). Reviewer ≠ implementer nawet gdy ten sam vendor modelu.
- **Structured output.** `ok:true` + artefakt (plan.json / diff receipt / verdict) albo `ok:false` + reason enum. Brak limbo chat.
- **Activity retry ≠ blind re-prompt.** Temporal/Inngest może ponowić Activity przy crashu infrastruktury; semantyka „napraw testy” to **nowy** step zaplanowany przez Workflow po `run_tests` fail — z `failure_log` w input.
- **Meat ≡ AI.** Ten sam schema seat; kto wypełni SO nie zmienia krawędzi.
- **Handoff contract.** Leave = `{step_id, ok, artifact_ref, reason?, usage}`; Workflow zapisuje w Event History i idzie dalej DET ścieżką.
