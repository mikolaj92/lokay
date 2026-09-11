# Subgraph: ticket-to-pr

**Theme:** labeled ticket → implement → local test → commit/push → open PR.  
**Mode mix:** DET spine; AGENT SO tylko na implement. **Zero merge.**

## Flow

```mermaid
flowchart TD
  A([enter]) --> B[DET: pick one ready-for-agent]
  B --> C{labeled issue?}
  C -->|none| Z([leave: idle])
  C -->|one| D[DET: worktree / branch from ticket id]
  D --> E[AGENT SO: implement]
  E --> F[DET: run verification from ticket]
  F --> G{green?}
  G -->|no — budget left| E
  G -->|no — exhausted| X([leave: fail / skip])
  G -->|yes| H[DET: commit + push]
  H --> I[DET: open PR Closes #N]
  I --> J([leave: PR open — no merge here])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  class B,D,F,H,I det
  class E agent
```

## Notes

- **Coder ≠ merge.** Ten podgraf kończy na otwartym PR. Przycisk merge żyje dopiero w OPA gate.
- **Label = start.** Zero „weź z czatu”. Brak etykiety → idle.
- **Implement = AGENT SO.** `{ok, summary, files_touched}` albo `{ok:false, reason}` → skip bez limbo theatre.
- **Bounded local repair.** Czerwony test → ograniczona pętla w tym samym liściu; potem fail. Bez zagnieżdżonego SDLC.
- **DET git/PR.** Nazwa brancha, commit message z ticket id, `gh pr create` — skrypt.
- **Handoff:** `{pr, head_sha, base, ticket_id, files_touched}` → optional review / OPA pack.
