# Subgraph: git-pr

**Theme:** branch → commit(y) → push → otwórz pull request.  
**Mode mix:** wyłącznie DET — deterministic git + PR plumbing.

## Flow

```mermaid
flowchart TD
  A([enter: code ready]) --> B[DET: ensure clean workspace]
  B --> C[DET: create / checkout branch]
  C --> D[DET: stage + commit]
  D --> E{more commits needed?}
  E -->|yes — still part of implement loop| F[signal: back to implement]
  F --> Z0([leave: need more code])
  E -->|no| G[DET: push to origin]
  G --> H[DET: open pull request]
  H --> I([leave: PR open])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,D,G,H det
```

## Notes

- **Clean stages: git then PR.** SOUL steps 5–8 as one DET subgraph with many small atoms.
- **Branch naming is script.** Deterministic from ticket ID + slug — no ad-hoc invention.
- **Commits stay DET.** Message from ticket ID + short summary; no release-note novels unless hooks require.
- **Open PR is DET.** Template + create; no AGENT writing the PR as a second product.
- **If more code is needed,** leave with signal back to implement — do not hide coding inside git.
- **Handoff contract.** Output = `{branch, commit_shas, pr_url}` for critical-review.
