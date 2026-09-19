# Subgraph: build-review-fix

**Theme:** Lucius build w worktree → adversarial review → fix loop.  
**Mode mix:** DET worktree/plumbing + AGENT leaves (build / review / fix). Reviewer ≠ builder.

## Flow

```mermaid
flowchart TD
  A([enter: approved plan]) --> B[DET: worktree add + lock]
  B --> C[AGENT: Lucius build SO — implement in worktree]
  C --> D[DET: run declared tests / collect evidence]
  D --> E[AGENT: adversarial review SO — other engine/session]
  E --> F{verdict?}
  F -->|block / P0| G[AGENT: fix SO — address valid findings]
  G --> H[DET: re-test evidence]
  H --> E
  F -->|ok + evidence| I[DET: commit / push branch]
  I --> J([leave: ready to ship → spine])
  F -->|budget exhausted| K([leave: escalate / hold PR draft])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  class B,D,H,I det
  class C,E,G agent
  class J,K stop
```

## Notes

- **Isolated worktree.** Code-changing + review roles na osobnych worktree; lock + recovery wokół lifecycle (alfred).
- **Independent review.** Adversarial leaf ≠ ten sam chat co Lucius. Preferowany inny silnik (Claude↔Codex↔OpenCode).
- **Evidence on PR path.** Verification evidence domyślnie z build/test — człowiek może sprawdzić co biegło.
- **Fix → review only.** Po fix zawsze ponowny review; **zakaz** skoku do `ship` z niesprawdzonym diffem.
- **Bounded attempts.** Halt repeated failing runs — nie nieskończony Ralph w środku stage.
- **Vacuous-green refusal.** Brak zadeklarowanych testów = hold/warn w evidence, nie silent pass do ship.
- **Handoff.** `{branch, head_sha, evidence, review_so, fix_attempts}` → ship-merge-gate.
