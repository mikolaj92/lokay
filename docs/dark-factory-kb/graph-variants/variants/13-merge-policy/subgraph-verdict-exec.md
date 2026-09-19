# Subgraph: verdict-exec

**Theme:** po decyzji policy — CI wait + **DET** merge albo hold. Jedyny miejsca z `merge` w wariancie 13.  
**Mode mix:** 100% DET. Zero AGENT.

## Flow

```mermaid
flowchart TD
  A([enter: policy route + optional risk]) --> B[DET: wait / fetch required checks]
  B --> C{CI green?}
  C -->|no| HOLD[DET: hold — leave PR open]
  HOLD --> H([leave: hold / fix loop])
  C -->|yes| P{policy branch}
  P -->|Off| HUM[DET: leave open — human owns merge]
  HUM --> H
  P -->|Always| AL{narrow allowlist? docs/lockfile/tiny fix+test}
  AL -->|yes + CI oracle| M[DET: merge + close issue]
  AL -->|no / out of allowlist| HUM
  P -->|Classify| R{risk low from classify path?}
  R -->|low| M
  R -->|high| HUM
  M --> K([leave: merged])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class B,HOLD,HUM,AL,R,M det
  class K ok
  class H stop
```

## Notes

- **Jedyny merge seat.** Coder-ceiling nie merguje; classify-so nie merguje; policy-star tylko routuje. Tu skrypt wykonuje `allow → merge` albo `hold`.
- **Fail-closed.** Czerwone CI, brak checks, konflikt → hold. Agent nie nadpisuje.
- **Always wąski.** Nawet przy Always: poza allowlistą → human (jak Off).
- **Classify high = Off behavior.** Świadomy hold — energia człowieka na architekturę / QA, nie na klepanie kolejki.
- **Handoff contract.** `{merged:true, merge_sha, issue_closed}` albo `{merged:false, policy: Off|Classify|Always, reason, pr_url}`.
- **NOT L5.** Auto-merge gdy polityka zielona ≠ lights-out bank.
