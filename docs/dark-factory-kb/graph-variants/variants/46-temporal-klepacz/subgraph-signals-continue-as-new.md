# Subgraph: signals-continue-as-new

**Theme:** Durable HITL przez Temporal Signals; MergePolicy Off|Classify|Always; `continueAsNew` jako granica ticketa.  
**Mode mix:** HITL Signals + DET policy + DET CAN.

## Flow

```mermaid
flowchart TD
  A([enter: PR open / policy gate]) --> B{MergePolicy?}
  B -->|Always + checks green| M[DET Activity: merge]
  B -->|Classify| C[DET: risk from labels/paths]
  C -->|low + green| M
  C -->|high / unknown| W
  B -->|Off| W[DET: waitCondition on Signals]
  W --> S{Signal?}
  S -->|approve| M
  S -->|deny / changes_requested| BACK([yield: llm Implement repair])
  S -->|timeout| ESC([leave: escalate needs-human])
  M --> E{merged?}
  E -->|yes| TERM[DET: ticket terminal done]
  E -->|blocked| ESC
  TERM --> CAN{more tickets in worker?}
  CAN -->|yes| NEXT[DET: continueAsNew nextTicketId]
  CAN -->|no| DONE([leave: done Msquare])
  NEXT --> OUT([leave: fresh Workflow history])
  W --> PARK[DET: park — no CPU / no tokens]
  PARK --> S

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef human fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  class M,C,TERM,NEXT,PARK det
  class W,S human
```

## Notes

- **Signals, not Inngest waitForEvent.** `defineSignal("approve"|"deny"|"changes_requested")` + `workflow.waitCondition` / `condition`. Opcjonalnie `defineUpdate` dla synchronicznego HITL.
- **Wait is durable.** Misja śpi w Temporal; Event History trzyma park — zero tokenów na orkiestrację.
- **Policy is CODE.** Off|Classify|Always = atom DET (KLEPACZ.md). LLM Review komentuje; nie jest jedyną bramką merge.
- **CAN per ticket.** Po done/escalate/skip: `continueAsNew(nextTicketId)` albo return + nowy `StartWorkflow`. Cel: świeża historia per ticket, bez bloatu przy kolejce / repair loops.
- **Changes → bounded Implement.** Deny nie restartuje od hydrate; Workflow woła Implement z review comments.
- **Handoff.** Leave done = `{pr, merged_sha}`; escalate = `{reason, pr_url}`; CAN = `{nextTicketId}`; yield Implement = `{comments, attempt}`.
