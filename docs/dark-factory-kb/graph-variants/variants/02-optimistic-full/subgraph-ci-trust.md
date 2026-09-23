# Subgraph: ci-trust

**Theme:** poczekaj na checks; ufaj zielonemu CI; jeden lekki nudge przy rzadkim flaky.  
**Mode mix:** wszystko DET. Optymistyczny babysit — nie full fail-closed circus (03).

## Flow

```mermaid
flowchart TD
  A([enter: PR open]) --> B[DET: poll CI / required checks]
  B --> C{status?}
  C -->|pending| B
  C -->|green| D([leave: CI trusted green])
  C -->|red| E{nudge budget left?}
  E -->|yes ≤1| F[DET: re-run failed jobs once]
  F --> B
  E -->|exhausted| G([leave: nudge implement-ship])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef warn fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,F det
  class D ok
  class G warn
```

## Notes

- **Trust the green path.** Default happy path = green bez dramatu.
- **One flaky nudge.** Re-run failed jobs max 1×; potem wróć do implement-ship z feedbackiem — nie limbo, nie nieskończony poll.
- **CI is oracle.** Agent nie override'uje czerwonego builda.
- **No stuck-PR survey theatre.** Optymista zakłada sensowne okna CI; timeout → leave z receipt do ship/review policy.
- **Handoff:** `{ci: green, pr}` albo `{ci: red_after_nudge, logs_summary}` → top-level wraca do ship.
