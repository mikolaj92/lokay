# Subgraph: git-pr

**Theme:** **all git / PR = DET** — branch, commit(s), push, open PR. Zero agent tool-calling na gicie.  
**Mode mix:** pure DET. Agenty tu nie wchodzą.

## Flow

```mermaid
flowchart TD
  A([enter: code ready in worktree]) --> B[DET: create / checkout branch from hint]
  B --> C[DET: stage + commit message from ticket+summary]
  C --> D{more atomic commits policy?}
  D -->|yes split| C
  D -->|no| E[DET: push origin]
  E --> F[DET: open_pr template + create]
  F --> G[DET: attach labels / link issue]
  G --> H([leave: PR open])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,E,F,G det
```

## Invariant: DET-only git/PR

| Atom | Who |
|------|-----|
| branch create/checkout | DET |
| stage / commit | DET |
| push origin | DET |
| open pull request | DET |
| label / link issue | DET |

Agent **nie** woła `gh` / `git` z tool-callingu w tym wariancie. Jeśli hook wymaga wiadomości — bierze ją z ticket ID + implement summary (deterministyczny szablon).

## Notes

- **Implementer ceiling was code.** Ten subgraph jest jedynym miejscem, gdzie powstaje remote branch i PR.
- **One ticket → one PR.** Brak batchowania wielu issue w jeden PR.
- **Fail closed.** Push/PR atom fail → stop pass; nie „agent naprawi remote”.
- **Draft vs ready** zależy od MergePolicy / review policy na wyższym poziomie — atom `open_pr` jest zawsze DET.
- **Handoff contract.** Output = `{pr_url, branch, commit_shas, summary}` dla review-merge.
- **Polish:** cała nuda gita i PR to skrypt — dokładnie po to jest dual-light-agents.
