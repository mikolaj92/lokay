# Subgraph: implement-ship

**Theme:** implement → local checks → commit(s) → push → open PR.  
**Mode mix:** AGENT implement; DET git/PR plumbing.  
**Ceiling:** open PR (`Closes #N`). Merge żyje w review-merge.

## Flow

```mermaid
flowchart TD
  A([enter: issue + branch + optional plan]) --> B[AGENT: implement]
  B --> C[DET: run local checks / test_command]
  C --> D{green?}
  D -->|no bounded| B
  D -->|no exhausted| F([leave: fail escape])
  D -->|yes| E[DET: stage + commit]
  E --> G{more commits needed?}
  G -->|yes| B
  G -->|no| H[DET: push origin]
  H --> I[DET: open PR Closes N]
  I --> J([leave: PR open])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class C,E,H,I det
  class B agent
```

## Notes

- **Implement = jedyny entropy sink kodu.** Plan (jeśli był) jest inputem, nie drugim mózgiem orkiestrującym tool-calling.
- **Bounded repair.** Lokalny fail → wróć do implement z limitem; po wyczerpaniu fail escape + receipt — nie nieskończona pętla.
- **Commits DET.** Message z ticket id + krótkie summary; bez release-note powieści.
- **One PR.** `Closes #<issue>` — K=1 zachowane do końca.
- **Nie pickujemy tu.** Ten podgraf nie listuje issues i nie zmienia labeli startowych.
- **Handoff:** `{pr_url, branch, commit_shas, summary}` → review-merge.
