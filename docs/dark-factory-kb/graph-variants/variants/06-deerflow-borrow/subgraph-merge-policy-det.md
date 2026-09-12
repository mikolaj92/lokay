# Subgraph: merge-policy-det

**Theme:** Merge Policy **DET ours** — Off \| Classify \| Always. LLM nie klika merge.  
**Mode mix:** 100% DET po otwartym PR (coder ceiling z agent-leaf-gh).

## Flow

```mermaid
flowchart TD
  A([enter: PR open Closes N]) --> B[DET: wait / fetch required checks]
  B --> C{CI green?}
  C -->|no| HOLD[DET: hold — leave PR open]
  HOLD --> Z([leave: hold / human or fix loop])
  C -->|yes| E{Merge Policy knobs — OURS}
  E -->|Off| HUM[DET: leave open for human merge]
  HUM --> H([leave: human owns merge])
  E -->|Always| G{narrow allowlist? docs/lockfile/tiny fix+test}
  G -->|yes + CI oracle| M[DET: merge + close issue]
  G -->|out of allowlist| HUM
  E -->|Classify| R{risk DET: size / paths / labels / review.risk}
  R -->|low| M
  R -->|high| HUM
  M --> K([leave: merged — DET ours])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,HOLD,HUM,G,R,M det
```

## Notes

- **DET ours.** Gałka per repo z kanonu KLEPACZ / ready-for-agent: **Off / Classify / Always**. To nie jest prompt „czy zmergować?” i nie jest polityka DeerFlow — DeerFlow kończy na `gh` writeback; **merge authority zostaje nasza**.
- **Default Off.** Klepacz (meat lub AI) pisze PR; człowiek merguje. Auto-merge = polityka, nie religia.
- **Classify = reguły DET.** Size, chronione ścieżki (auth/billing/schema), labels, opc. `review.risk` z UUID5 reviewera — skrypt. Nie LLM classifier.
- **Always = wąski.** Tylko gdy CI jest wyrocznią. `reject`/`high` z review → never Always.
- **Coder ≠ merge.** Implement leaf (nawet z `gh pr create`) nie ma przycisku merge. Osobny węzeł po CI.
- **Fail-closed.** Czerwone CI, brak required checks, konflikt → hold. Zero agent override.
- **SOUL.** Przy Off / high Classify energia człowieka idzie w architekturę i niewygodne pytania QA — nie w klepanie kolejki. NOT L5.
- **Handoff contract.** `{merged:true, merge_sha, issue_closed}` albo `{merged:false, policy: Off|Classify|Always, reason, pr_url}`.
