# Subgraph: hitl-wait

**Theme:** Durable HITL — `step.waitForEvent` / Workflow Signal; MergePolicy Off|Classify|Always.  
**Mode mix:** HITL + DET policy. LLM nie jest sędzią merge.

## Flow

```mermaid
flowchart TD
  A([enter: PR open / policy gate]) --> B{MergePolicy?}
  B -->|Always + checks green| M[DET Activity: merge]
  B -->|Classify| C[DET: risk class from labels/paths]
  C -->|low + green| M
  C -->|high / unknown| W
  B -->|Off| W[DET: waitForEvent / Signal approve|deny]
  W --> D{signal?}
  D -->|approve| M
  D -->|deny / changes_requested| BACK([yield: llm-activity repair])
  D -->|timeout| ESC([leave: escalate needs-human])
  M --> E{merged?}
  E -->|yes| DONE([leave: done])
  E -->|blocked| ESC
  W --> F[DET: park Workflow — no CPU burn]
  F --> D

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef human fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  class M,C,F det
  class W,D human
```

## Notes

- **Wait is durable.** Inngest `step.waitForEvent("pr/approved")` / Temporal `wait_condition` + Signal — misja śpi w historii, nie w RAM agenta.
- **Policy is CODE.** Off|Classify|Always = atom DET (jak KLEPACZ.md). LLM review może *komentować*; nie jest jedyną bramką merge.
- **Human owns outcome when Off.** Domyślny klepacz: Off → człowiek approve/deny; factory nie self-merge w limbo.
- **Changes → bounded LLM step.** Deny nie restartuje całego Workflow od pick; Workflow planuje repair Activity z komentarzami jako input.
- **Handoff.** Leave done = `{pr, merged_sha}`; escalate = `{reason, pr_url}`; yield llm-activity = `{review_comments, attempt}`.
