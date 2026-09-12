# Subgraph: artifacts-pr

**Theme:** Prefect artifacts + **PR ceiling** + HITL (`pause_flow_run`) + MergePolicy.  
**Mode mix:** DET observe + HITL. LLM nie jest sędzią merge; coder kończy na `open_pr`.

## Flow

```mermaid
flowchart TD
  A([enter: after impl / open_pr]) --> B[DET: create_markdown_artifact plan optional]
  B --> C[DET: create_markdown_artifact impl_receipt]
  C --> D{PR already open?}
  D -->|no| E[DET @task: open_pr — coder ceiling]
  D -->|yes| F
  E --> F[DET: create_link_artifact pr_url]
  F --> G{MergePolicy?}
  G -->|Always + checks green| M[DET @task: merge]
  G -->|Classify| CL[DET: risk class labels/paths]
  CL -->|low + green| M
  CL -->|high / unknown| W
  G -->|Off| W[DET: pause_flow_run wait Approval]
  W --> H{human decision?}
  H -->|approve| M
  H -->|deny / changes| BACK([yield: task-llm implement])
  H -->|timeout| ESC([leave: escalate needs-human])
  M --> I{merged?}
  I -->|yes| DONE([leave: done])
  I -->|blocked| ESC
  W --> PARK[DET: park flow-run — no tokens]
  PARK --> H

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef human fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  class B,C,E,F,CL,M,PARK det
  class W,H human
```

## Notes

- **Artifacts ≠ edges.** Markdown/link w Prefect UI = audyt dla człowieka; nie sterują kolejnym `@task`.
- **PR ceiling.** Po `open_pr` kończy się slot implementera. Żadnego LLM-merge, żadnego „agent domyka fabrykę”.
- **Pause is durable.** `pause_flow_run` — misja śpi w Prefect, nie w RAM modelu.
- **Policy is CODE.** Off|Classify|Always jak KLEPACZ.md. Domyślnie Off → człowiek.
- **Changes → bounded re-entry.** Deny nie restartuje Deployment od zera; `@flow` woła ponownie `implement` z komentarzami (budżet N).
- **Handoff.** Leave done = `{pr, merged_sha?, artifact_keys}`; escalate = `{reason, pr_url}`; yield task-llm = `{review_comments, attempt}`.
