# Subgraph: step-run-llm

**Theme:** LLM siedzi **wewnątrz** jednego `step.run` — wypełnia SO; nie routuje function body.  
**Mode mix:** AGENT leaf only. Function decyduje *kiedy* ten step; wnętrze kroku decyduje *jak* w budżecie.

## Flow

```mermaid
flowchart TD
  A([enter: LLM step.run scheduled]) --> B[DET: load prompt_ref + schema + ticket_ctx]
  B --> C[DET: enforce timeout / token / tool budget]
  C --> D{leaf kind?}
  D -->|plan| P[AGENT SO: plan files / tests / stop_if]
  D -->|implement| I[AGENT SO: edit in worktree]
  D -->|pr-review| R[AGENT SO: critical review verdict]
  D -->|repair| F[AGENT SO: bounded fix from failure_log]
  P --> E{ok structured?}
  I --> E
  R --> E
  F --> E
  E -->|ok:true| OK[DET: return artifact → memo]
  E -->|ok:false| NO[DET: return fail reason enum]
  OK --> OUT([leave: resume function body])
  NO --> OUT
  C -->|budget hard stop| KILL[DET: throw / fail step]
  KILL --> OUT

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,C,OK,NO,KILL det
  class P,I,R,F agent
```

## Notes

- **Not a router.** Model nie wybiera „co dalej”. Nie woła `step.sendEvent` żeby przestawić FSM, nie decyduje o merge, nie skacze po labelach.
- **One step, one leaf.** Plan / implement / review / repair = osobne `step.run` (osobne memo). Reviewer ≠ implementer nawet gdy ten sam vendor modelu.
- **Structured output.** `ok:true` + artefakt (plan.json / diff receipt / verdict) albo `ok:false` + reason enum. Brak limbo chat.
- **Infra retry ≠ blind re-prompt.** Inngest może ponowić padnięty `step.run` przy crashu; semantyka „napraw testy” to **nowy** nazwany step zaplanowany przez function body po `run-tests` fail — z `failure_log` w input.
- **Meat ≡ AI.** Ten sam schema seat; kto wypełni SO nie zmienia krawędzi.
- **Handoff contract.** Leave = `{step_id, ok, artifact_ref, reason?, usage}`; function body zapisuje w memo i idzie dalej DET ścieżką.
