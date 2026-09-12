# Subgraph: workflow-as-code

**Theme:** Temporal Workflow = deterministyczny kod; Event History = źródło prawdy; `proxyActivities` = jedyny I/O.  
**Mode mix:** DET only. Zero LLM w ciele Workflow.

## Flow

```mermaid
flowchart TD
  A([enter: StartWorkflow ticketId]) --> B[DET: bind runId + ticketId]
  B --> C[DET: proxyActivities DET + LLM seats]
  C --> D[(Event History)]
  D --> E[DET: schedule next Activity name]
  E --> F{Activity kind?}
  F -->|CODE hydrate/plan/worktree/test/git/pr/merge| DET([yield: det-activities])
  F -->|Implement or Review only| LLM([yield: llm-implement-review])
  F -->|wait Signal| HITL([yield: signals-continue-as-new])
  F -->|ticket terminal| CAN([yield: continueAsNew / done])
  DET -->|result recorded| D
  LLM -->|result recorded| D
  HITL -->|Signal recorded| D
  E --> G{history / ticket done?}
  G -->|next ticket| CAN
  G -->|continue same ticket| F

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef store fill:#1a1a2a,stroke:#6a6ab8,color:#e8e8ff
  class B,C,E det
  class D store
```

## Notes

- **Replay-safe.** Workflow czyta historię + wyniki Activities. Żadnych zegarów wall-clock / LLM / niestabilnych map w ciele (Temporal nondeterminism).
- **Orkiestrator nie myśli.** Kolejność klepacza stała: hydrate → planTemplate(DET) → worktree → implement → test → (repair×N) → openPr → review → signal/policy → merge|CAN.
- **Durability ≠ agent memory.** Context window modelu nie jest stanem misji.
- **One Workflow occupancy per ticket.** K=1 egzekwowane DET Activity przed Implement.
- **Handoff.** Yield det = `{activity, idempotency_key, input_ref}`; yield llm = `{seat: implement|review, attempt, ctx}`; yield hitl = `{signals, pr_ref, policy}`.
