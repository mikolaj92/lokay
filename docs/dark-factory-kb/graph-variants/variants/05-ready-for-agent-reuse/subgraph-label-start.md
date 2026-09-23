# Subgraph: label-start

**Theme:** etykieta `ready-for-agent` = jedyny start (reuse z berenddeboer/ready-for-agent).  
**Mode mix:** 100% DET. Agent nie wybiera pracy.

## Flow

```mermaid
flowchart TD
  A([enter: harness tick]) --> B[DET: list issues with label ready-for-agent]
  B --> C{authorship filter?}
  C -->|default: only my issues| D[DET: filter by author]
  C -->|org-wide allowlist| D2[DET: filter by allowlist]
  D --> E{any labeled?}
  D2 --> E
  E -->|none| F[DET: record idle]
  F --> Z([leave: none])
  E -->|≥1| G[DET: pick exactly one K=1]
  G --> H{repo occupied?}
  H -->|live launch / open cell| I[DET: defer]
  I --> Z2([leave: defer])
  H -->|free| J[DET: lock claim + payload]
  J --> K([leave: issue ready])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,D,D2,F,G,I,J det
```

## Notes

- **Reuse fidelity.** Harness ready-for-agent pokazuje tylko labelowane; to samo tu — lista DET, nie triage AGENT.
- **Label ≠ chat.** Cytat kanonu: *You design, you architect, you verify where needed — the harness removes the babysitting between issue and merged PR.* Człowiek projektuje issue; klepacz startuje od etykiety.
- **K=1.** Jedna misja naraz per repo/occupancy; reszta czeka w kolejce labelowanej.
- **Fail closed.** Brak labeli → idle receipt. Nie wymyślaj ticketów, nie sięgaj po unlabeled „bo wygląda na gotowe”.
- **Agent-ready gate (opc. DET).** Twardy check szablonu (Outcome / In-Out scope / Acceptance / Allowed / Ask-or-stop / Verification) może zablokować claim — taniej niż „lepszy model” (KLEPACZ.md).
- **Handoff contract.** Output = `{issue_id, title, body, labels, base_ref, claim_token}` albo `{none|defer}`.
