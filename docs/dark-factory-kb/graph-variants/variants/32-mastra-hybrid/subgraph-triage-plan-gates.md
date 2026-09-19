# Subgraph: triage-plan-gates

**Theme:** **Staged half** — Triage Q&A + Planning approve/edit zanim wolny sandbox.  
**Mode mix:** HITL primary; optional AGENT assist SO (pytania / draft planu). Agent **nie** omija bramek.

## Flow

```mermaid
flowchart TD
  A([enter: work item Triage or Planning]) --> B{stage?}
  B -->|Triage| T1[AGENT optional: draft clarifying questions]
  T1 --> T2[HITL: human answers in UI / thread]
  T2 --> T3{resolved / enough context?}
  T3 -->|no| T1
  T3 -->|reject / wontfix| X[DET: mark cancelled / park]
  T3 -->|yes| T4[DET: advance → Planning]
  B -->|Planning| P1[AGENT optional: draft plan SO]
  T4 --> P1
  P1 --> P2[HITL: human approve / edit plan]
  P2 --> P3{decision?}
  P3 -->|edit| P1
  P3 -->|deny| X
  P3 -->|approve| OK[DET: pin plan artifact + unlock Building]
  OK --> OUT([leave: sandbox-build])
  X --> IDLE([leave: idle / Done-cancelled])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef hitl fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  class T3,T4,P3,OK,X det
  class T1,P1 agent
  class T2,P2 hitl
```

## Notes

- **Bramki są prawdą hybrydy.** Bez approve planu **nie** ma free sandbox build — to odróżnia hybrid od „od razu koduj”.
- **Assist ≠ authority.** SO pyta / draftuje; człowiek zamyka Triage i Planning.
- **Plan artefact.** Outcome / Steps / Files / Test hint / Risks / Ask-or-stop — pin w work item; Building czyta to jako kontrakt.
- **Reversible.** Deny / park wraca do idle bez spalania sandboxa.
- **Handoff.** Leave = `{work_item_id, plan_ref, stage: Building, approved_by}`.

## Structured output (plan draft skrót)

```json
{
  "ok": true,
  "goal": "...",
  "steps": ["..."],
  "files": ["..."],
  "test_command": "...",
  "risks": ["..."],
  "stop_if": ["auth", "migration", "public_api_break"]
}
```
