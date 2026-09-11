# Subgraph: ci-review-station

**Theme:** stacje `ci` + `review` — bounded CI repair, human PR review, Jira finalize.  
**Mode mix:** DET CI poll + bounded AGENT `ci_repair_patch` + HITL review. Agent nie merżuje.

## Flow

```mermaid
flowchart TD
  A([enter: station=ci + pr_url]) --> B[DET: poll CI / checks]
  B --> C{CI?}
  C -->|red + repair_used < N| D[AGENT SO: ci_repair_patch]
  D --> E[DET: push fix commit]
  E --> B
  C -->|red + budget exhausted| FAIL([leave: failed / escalate])
  C -->|green| F[DET: advance station→review]
  F --> G[AGENT SO optional: pr_review_critique]
  G --> H{HITL: human PR review?}
  H -->|request changes| D2[bounded return → ci/impl per policy]
  D2 --> B
  H -->|approve| I[DET: merge_policy Off|Classify|Always]
  I --> J{policy / human merge?}
  J -->|no merge yet| HOLD([leave: PR open, await human])
  J -->|merged| K[DET: Jira summary + metrics]
  K --> L([leave: done])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef hitl fill:#2a1a3a,stroke:#8a5ab8,color:#f3e8ff
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class B,E,F,I,K det
  class D,G agent
  class H hitl
  class FAIL,HOLD stop
```

## Notes

- **CI jest wyrocznią.** Zieloność = runner / checks, nie opinia modelu. Repair slot dostaje logi + failing tests; N z MANIFEST (`ci_repair_n`).
- **Review ≠ implementer.** Opcjonalny critique SO to osobna sesja / osobny leaf; human zawsze trzyma merge button (forge-sdlc: always human PR review).
- **MergePolicy.** Off = tylko otwarty PR; Classify = SO klasyfikuje + DET; Always = auto po approve+green — nadal nie L5 na prod bez human gate w manifeście.
- **Jira finalize.** Summary + metrics to DET po merge/approve — journal zamyka run.
- **Handoff końcowy.** `{pr_url, ci:green, review:approved, merged?:bool, jira_updated:true}` albo failed/hold.

## Structured output — `ci_repair_patch`

```json
{
  "ok": true,
  "diffs": [{"path": "src/api.py", "patch": "..."}],
  "root_cause": "missing null check from CI log",
  "confidence": "medium"
}
```

```json
{ "ok": false, "reason": "cannot_fix|flaky_unknown|needs_human" }
```

## Structured output — `pr_review_critique` (optional)

```json
{
  "ok": true,
  "verdict": "comment|request_changes|approve_suggest",
  "findings": [{"severity": "arch", "note": "prefer existing helper"}],
  "merge_safe_guess": false
}
```

> `approve_suggest` ≠ merge. Merge wykonuje człowiek / DET merge_policy po HITL.
