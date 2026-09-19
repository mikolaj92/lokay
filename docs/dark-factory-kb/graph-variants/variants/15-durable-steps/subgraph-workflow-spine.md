# Subgraph: workflow-spine

**Theme:** Temporal Workflow / Inngest function = deterministyczny szkielet; Event History = źródło prawdy.  
**Mode mix:** DET only. Zero LLM w ciele Workflow.

## Flow

```mermaid
flowchart TD
  A([enter: ready-for-agent event]) --> B[DET: StartWorkflow / Inngest fn]
  B --> C[DET: bind ticket id + run id]
  C --> D[(Event History / step memo)]
  D --> E[DET: schedule next step id]
  E --> F{step kind?}
  F -->|CODE Activity| DET([yield: det-steps])
  F -->|LLM Activity| LLM([yield: llm-activity])
  F -->|wait / signal| HITL([yield: hitl-wait])
  F -->|terminal ok| DONE([leave: done])
  F -->|terminal fail| ESC([leave: escalate])
  DET -->|Activity result recorded| D
  LLM -->|Activity result recorded| D
  HITL -->|signal / event recorded| D
  E --> G{history too long?}
  G -->|yes| H[DET: continue-as-new]
  H --> D
  G -->|no| F

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef store fill:#1a1a2a,stroke:#6a6ab8,color:#e8e8ff
  class B,C,E,H det
  class D store
```

## Notes

- **Replay-safe.** Workflow body czyta tylko historię + wyniki Activities. Żadnych losowych zegarów / LLM / niestabilnych map w ciele (Temporal nondeterminism).
- **Orkiestrator nie myśli.** `schedule next step id` = stała kolejność klepacza (pick → worktree → plan → implement → test → PR → review → merge_policy) + wyniki diamondów budżetu.
- **Durability ≠ agent memory.** Context window modelu nie jest stanem misji. Restart workera = replay Event History.
- **One Workflow per ticket.** K=1 occupancy egzekwowane przed startem lub jako pierwszy DET step; nie fan-out katalogu w środku runu.
- **Handoff contract.** Yield det-steps = `{step_id, activity_name, idempotency_key, input_ref}`; yield llm-activity = `{step_id, prompt_ref, schema, ticket_ctx, attempt}`; yield hitl = `{wait_key, pr_ref, policy}`.
