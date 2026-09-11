# Subgraph: review-complete

**Theme:** Review station (osobna sesja) → human merge → Done + sandbox teardown.  
**Mode mix:** HITL merge authority; optional AGENT review SO; DET completion.

## Flow

```mermaid
flowchart TD
  A([enter: PR on Review station]) --> B[DET: ensure review session ≠ build session]
  B --> C[AGENT optional: critical review SO on PR diff]
  C --> D[HITL: human inspect / request changes / merge]
  D --> E{decision?}
  E -->|changes requested| F[DET: label / comment → return Building]
  E -->|reject / close| G[DET: close path + mark work cancelled]
  E -->|merge| H[DET: merge via human / policy Off default]
  F --> OUTB([leave: sandbox-build])
  H --> I{work actually done? multi-PR?}
  I -->|more work| J[DET: keep work open / next plan gate]
  I -->|complete| K[DET: stage Done + teardown sandbox]
  G --> K2[DET: teardown sandbox]
  K --> DONE([leave: done Msquare])
  K2 --> DONE
  J --> OUTP([leave: triage-plan-gates])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef hitl fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  class B,E,F,G,H,I,J,K,K2 det
  class C agent
  class D hitl
```

## Notes

- **Reviewer ≠ implementer.** Osobna sesja / opcjonalnie inny model — duch Mastra „review item gets its own session”.
- **Merge ≠ auto Done.** Jedno work item może wymagać >1 PR; completion sprawdza „czy request done?”, nie tylko „czy branch zmergowany”.
- **Human owns merge.** Domyślnie Off; Classify/Always tylko jako świadoma polityka klepacza — nie L5.
- **Teardown.** Po terminal (Done / cancelled) zdejmij sandbox — hybrid free half nie zostawia zombie VM.
- **Handoff.** Leave = `{work_item_id, merged?, done?, sandbox_torn_down}`.

## Structured output (review SO skrót)

```json
{
  "verdict": "approve|changes|reject",
  "reasons": ["..."],
  "risk": "low|high",
  "architecture_flags": ["..."]
}
```
