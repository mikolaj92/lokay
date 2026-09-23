# Subgraph: ship-pr

**Theme:** faza 4 — po **pass** oracle: DET commit → push → open PR; merge policy.  
**Mode mix:** 100% DET (opc. osobny review SO poza tym wariantem — nie grade). Agent implement **nie** merżuje.

## Flow

```mermaid
flowchart TD
  A([enter: pass receipt + worktree tree]) --> B[DET: assert grade.pass && exit_code==0]
  B --> C{still pass?}
  C -->|no| X([leave: refuse ship])
  C -->|yes| D[DET: commit on branch ai/fix-N]
  D --> E[DET: push origin]
  E --> F[DET: open PR Closes issue + attach grade receipt]
  F --> G[DET: merge_policy Off|Classify|Always]
  G --> H{policy?}
  H -->|Off| HOLD([leave: PR open — human merge])
  H -->|Classify/Always per rules| M[DET: merge or hold]
  M --> DONE([leave: done])
  HOLD --> DONE

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,D,E,F,G,M det
  class X bad
  class DONE,HOLD ok
```

## Notes

- **Ship only on oracle pass.** Ponowny assert receipt przed commit — race / stale tree ⇒ refuse.
- **Coder ceiling = open PR.** Liść implement już się skończył w fazie 2; tu same atomy git/gh.
- **Receipt on PR.** Body / comment: `grade.json` summary (`pass`, `tests_run`, `seal_token` short) — audyt bez LLM prose judge.
- **MergePolicy.** Default **Off** (SOUL / human energy). Classify/Always = skrypt, nie prompt implementera.
- **No grade-by-reviewer-LLM as merge gate.** Opcjonalny krytyczny review (inna persona/wariant) ≠ zastępstwo sealed oracle.
- **Handoff.** `{pr_url, branch, head_sha, grade_receipt, merge_result|hold}`.
