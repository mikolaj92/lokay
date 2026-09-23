# Subgraph: worktree

**Theme:** fresh `git worktree` + branch + install — sandbox komórka Solvio / ready-for-agent.  
**Mode mix:** 100% DET. Zero LLM w setup komórki.

## Flow

```mermaid
flowchart TD
  A([enter: GHA in-progress]) --> B[DET: derive branch auto-fix/issue-N]
  B --> C[DET: git worktree add fresh path]
  C --> D[DET: checkout / create branch from default]
  D --> E[DET: install deps in worktree]
  E --> F{install OK?}
  F -->|no| G[DET: teardown + label *-failed]
  G --> Z([leave: fail])
  F -->|yes| H[DET: write cell context — issue + CLAUDE.md + allow paths]
  H --> I([leave: cell ready])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,C,D,E,G,H det
  class Z bad
```

## Notes

- **Reuse fidelity.** Solvio: Node `auto-fix-issue.mjs` + `git worktree`; JBS Phase Prepare = ten sam seat. Worktree obowiązkowy — nie brudny cwd głównego klona.
- **K=1.** Jeden ticket = jeden worktree = jeden branch (`auto-fix/issue-N` albo `fix/issue-N`). Occupancy blokuje drugi claim w gha-dispatch.
- **Kontekst wąski.** Następny liść czyta issue (repro/expected/actual z template JBS) + `CLAUDE.md` + allow paths — nie cały świat i nie historię czatu.
- **Install jest DET.** `pnpm i` / `npm i` / Makefile — skrypt z repo; fail = `*-failed`, nie „agent naprawi środowisko na ślepo”.
- **Cleanup.** Po `*-done` / `*-failed` / timeout: `git worktree remove` + branch GC — DET, nie domysł liścia.
- **Handoff contract.** `{worktree_path, branch, base_sha, issue_payload, allow_paths[]}` albo `{ok:false, reason:install|worktree}`.
