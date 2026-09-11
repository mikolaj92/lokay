# Subgraph: issue-trigger

**Theme:** etykieta `ready-for-agent` **lub** assign do Copilot = jedyny start (reuse Copilot cloud + ready-for-agent).  
**Mode mix:** 100% DET. Agent nie wybiera pracy.  
**Handoff in:** daemon / Copilot cloud tick.  
**Handoff out:** `{issue_id, title, body, labels, assignees, base_ref, claim_token}` albo `{none|defer}`.

## Flow

```mermaid
flowchart TD
  A([enter: cloud / harness tick]) --> B[DET: list issues labeled ready-for-agent OR assigned to Copilot]
  B --> C{authorship / allowlist filter?}
  C -->|default: my issues| D[DET: filter by author]
  C -->|org allowlist| D2[DET: filter by allowlist]
  D --> E{any candidates?}
  D2 --> E
  E -->|none| F[DET: record idle]
  F --> Z([leave: none])
  E -->|≥1| G[DET: pick exactly one K=1]
  G --> H{ephemeral slot occupied?}
  H -->|live host / open draft mission| I[DET: defer]
  I --> Z2([leave: defer])
  H -->|free| J[DET: lock claim + payload]
  J --> K{agent-ready template OK?}
  K -->|missing Outcome / Acceptance / stop_if| L[DET: skip underspecified]
  L --> Z3([leave: skip])
  K -->|ok| M([leave: issue ready])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class B,D,D2,F,G,I,J,L det
  class Z,Z2,Z3 stop
```

## Notes

- **Reuse fidelity.** Copilot coding agent startuje od assign/issue; ready-for-agent od label. Tu **OR** — ta sama DET lista, zero triage AGENT.
- **Label/assign ≠ chat.** Człowiek projektuje issue; klepacz/cloud startuje od markera. Nie „wygląda na gotowe”.
- **K=1.** Jedna misja naraz per repo/ephemeral occupancy; reszta czeka w kolejce marked.
- **Fail closed.** Brak kandydatów → idle. Underspecified template → skip + receipt, nie „lepszy model zgadnie”.
- **Agent-ready gate (DET).** Twardy check szablonu (Outcome / In-Out / Acceptance / Allowed / Ask-or-stop / Verification) — taniej niż retry na VM.
