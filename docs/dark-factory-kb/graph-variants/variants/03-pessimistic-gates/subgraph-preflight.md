# Subgraph: preflight

**Theme:** brudny worktree / brak labeli / stuck PR — fail-closed przed jakąkolwiek pracą.  
**Mode mix:** 100% DET. Zero agenta. Zero „jakoś pojedziemy”.

## Flow

```mermaid
flowchart TD
  A([enter]) --> B[DET: worktree status]
  B --> C{clean?}
  C -->|dirty / unexpected files| X([leave: blocked → failure-escape])
  C -->|clean| D[DET: list ready-for-agent / ai:ready]
  D --> E{any labeled?}
  E -->|no / label vanished| X
  E -->|yes| F[DET: pick exactly one K=1]
  F --> G{acceptance + verify present?}
  G -->|missing| X
  G -->|yes| H[DET: survey open PRs / branches for same issue]
  H --> I{stuck PR or orphan branch?}
  I -->|stuck beyond bound| X
  I -->|orphan reclaimable| J[DET: reclaim or close per policy]
  J --> K{reclaim ok?}
  K -->|no| X
  K -->|yes| L[DET: worktree_add / branch from ticket id]
  I -->|none| L
  L --> M{branch created?}
  M -->|fail| X
  M -->|ok| N([leave: issue + branch + base_ref])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,D,F,H,J,L det
  class X bad
```

## Notes

- **Dirty = stop.** Nie stash theatre w grafie. Albo clean, albo escape z powodem `dirty_worktree`.
- **Label re-check.** Pick i start to dwa momenty; label może zniknąć. Brak = `missing_label`, nie limbo.
- **K=1.** Jeden ticket. Batch = nie.
- **Underspecified = blocked.** Brak acceptance / verification → escape `underspecified`. Nie plan-leaf, nie enrich.
- **Stuck PR survey.** Otwarty PR na ten sam issue z czerwonym CI / bez ruchu powyżej TTL → escape `stuck_pr` (albo reclaim jeśli policy na to pozwala).
- **Branch name = skrypt.** Z ID ticketa. Fail tworzenia brancha → escape, nie agent „napraw nazwę”.
- **No limbo labels.** Wyjścia: `blocked` z `reason` enum → failure-escape. Nigdy `ai:limbo`.
- **Handoff:** `{issue_id, branch, base_ref}` albo `{blocked:true, reason}`.
