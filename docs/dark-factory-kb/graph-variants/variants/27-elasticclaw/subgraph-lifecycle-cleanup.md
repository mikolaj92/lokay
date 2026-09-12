# Subgraph: lifecycle-cleanup

**Theme:** PR/CI/review ceiling → terminal stage → teardown sandbox.  
**Mode mix:** DET + opcjonalny HITL merge. Agent nie trzyma lifecycle.

## Flow

```mermaid
flowchart TD
  A([enter: PR tracked / ready_to_merge]) --> B{pr_conditions?}
  B -->|ci failing / changes-requested| BACK([leave: resume hub → fix leaf])
  B -->|ci passing + reviews clean + quiet_for| C[DET: ready_to_merge stage]
  C --> D{merge policy?}
  D -->|Off / high-risk| H[HITL: human approve]
  D -->|Classify| K[DET: classify risk band]
  K -->|low + Always band| M
  K -->|hold| H
  D -->|Always| M[DET: merge_pr via Server GH path]
  H -->|approve| M
  H -->|deny / changes| BACK
  M --> E[DET: trigger pr_merged → terminal]
  E --> F[DET: move_issue Done / labels]
  F --> G[DET: cleanup sandbox + revoke token]
  G --> DONE([leave: done Msquare])
  B -->|pr_closed no merge| N[DET: closed_no_merge terminal]
  N --> O[DET: move_issue Canceled]
  O --> G

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef hitl fill:#2a2a1a,stroke:#b8a04a,color:#fff8e8
  class C,K,M,E,F,G,N,O det
  class H hitl
```

## Notes

- **Coder ceiling = open PR.** Liść implement kończy się na PR; lifecycle (CI watch, review quiet window, merge) jest hub-owned.
- **`pr_conditions`.** `ci: passing`, `reviews: clean`, opcjonalnie `quiet_for` — deterministyczny compound state, nie „agent mówi że zielone”.
- **MergePolicy Off|Classify|Always.** Domyślnie Off / HITL; `merge_pr` przez Server path gdy polityka pozwala. Nie L5 lights-out.
- **Cleanup zawsze.** Po `merged` lub `closed_no_merge`: tear-down workspace, revoke installation token, zwolnij `concurrency_group`. Wyciek sandboxa = fail ops, nie „zostaw na później”.
- **Handoff contract.** Done = `{run_id, terminal, pr_ref, issue_status, cleaned:true}`.
