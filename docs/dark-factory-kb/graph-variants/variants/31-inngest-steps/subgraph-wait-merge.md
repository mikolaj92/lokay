# Subgraph: wait-merge

**Theme:** Durable HITL — `step.waitForEvent` + opcjonalnie `step.sendEvent`; MergePolicy Off|Classify|Always.  
**Mode mix:** HITL + DET policy. LLM nie jest sędzią merge.

## Flow

```mermaid
flowchart TD
  A([enter: PR open / policy gate]) --> B{MergePolicy?}
  B -->|Always + checks green| M[DET step.run: merge]
  B -->|Classify| C[DET: risk class from labels/paths]
  C -->|low + green| M
  C -->|high / unknown| W
  B -->|Off| W[DET: step.waitForEvent klepacz/pr.decision]
  W --> D{event decision?}
  D -->|approve| M
  D -->|deny / changes_requested| BACK([yield: step-run-llm repair])
  D -->|timeout| ESC([leave: escalate needs-human])
  M --> E{merged?}
  E -->|yes| DONE([leave: done])
  E -->|blocked| ESC
  W --> F[DET: park run — no CPU / no tokens]
  F --> D
  A --> S[DET: step.sendEvent request-review optional]
  S --> W

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef human fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  class M,C,F,S det
  class W,D human
```

## Notes

- **Wait is durable.** `step.waitForEvent("pr/approved", { event: "klepacz/pr.decision", match, timeout })` — misja śpi w Inngest, nie w RAM agenta.
- **Policy is CODE.** Off|Classify|Always = atom DET (jak KLEPACZ.md). LLM review może *komentować* w osobnym `step.run`; nie jest jedyną bramką merge.
- **Human owns outcome when Off.** Domyślny klepacz: Off → człowiek approve/deny; factory nie self-merge w limbo.
- **Changes → bounded LLM step.** Deny nie restartuje całego runu od claim; function body planuje repair `step.run` z komentarzami jako input.
- **Optional wake.** `step.sendEvent` może powiadomić reviewera / Slack / inny function — signal, nie router LLM.
- **Handoff.** Leave done = `{pr, merged_sha}`; escalate = `{reason, pr_url}`; yield step-run-llm = `{review_comments, attempt}`.
