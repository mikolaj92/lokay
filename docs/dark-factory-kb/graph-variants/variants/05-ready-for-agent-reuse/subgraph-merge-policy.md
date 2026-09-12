# Subgraph: merge-policy

**Theme:** Merge Policy **Off | Classify | Always** — gałka z ready-for-agent; DET only.  
**Mode mix:** 100% DET po otwartym PR. LLM nie klika merge.

## Flow

```mermaid
flowchart TD
  A([enter: PR open Closes N]) --> B[DET: wait / fetch CI status]
  B --> C{CI green / required checks?}
  C -->|no| D[DET: hold — leave PR open]
  D --> Z([leave: hold / fix loop])
  C -->|yes| E{Merge Policy knobs}
  E -->|Off| F[DET: leave open for human merge]
  F --> H([leave: human owns merge])
  E -->|Always| G{narrow allowlist? docs/lockfile/tiny fix+test}
  G -->|yes + CI oracle| M[DET: merge + close issue]
  G -->|no — out of allowlist| F
  E -->|Classify| R{risk DET: size / paths / labels / review.risk}
  R -->|low| M
  R -->|high| F
  M --> K([leave: merged])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,D,F,G,R,M det
```

## Notes

- **Reuse fidelity.** ready-for-agent Merge Policy per repo: **Off / Classify / Always**. To jest kanoniczna gałka KLEPACZ — nie prompt „czy zmergować?”.
- **Default Off.** Start bezpieczny: klepacz pisze PR, człowiek merguje. Auto-merge = polityka, nie religia (lekcja DEV: linie OK, decyzja zła → revert).
- **Classify = reguły DET.** Size, chronione ścieżki (auth/billing/schema), labels, `review.risk` z opcjonalnego SO — skrypt, nie LLM classifier.
- **Always = wąski.** Tylko gdy CI jest wyrocznią: docs, lockfile, bugfix z testem z issue. `reject`/`high` z review → never Always.
- **Coder ≠ merge.** Implementer (meat lub AI) nie ma przycisku merge. Osobny węzeł policy po CI.
- **Fail-closed.** Czerwone CI, brak required checks, konflikt → hold. Zero agent override.
- **Człowiek zostaje.** Przy Off / high Classify energia idzie w architekturę i niewygodne pytania QA — nie w babysitting kolejki (SOUL).
- **Handoff contract.** Output = `{merged:true, merge_sha, issue_closed}` albo `{merged:false, policy: Off|Classify|Always, reason, pr_url}`.
