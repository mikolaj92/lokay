# Subgraph: worktree

**Theme:** fresh worktree + install — sandbox komórka jak w ready-for-agent.  
**Mode mix:** 100% DET. Zero LLM w komórce setup.

## Flow

```mermaid
flowchart TD
  A([enter: issue claim]) --> B[DET: derive branch name from issue]
  B --> C[DET: git worktree add fresh path]
  C --> D[DET: checkout / create branch]
  D --> E[DET: install deps in worktree]
  E --> F{install OK?}
  F -->|no| G[DET: teardown + fail receipt]
  G --> Z([leave: fail])
  F -->|yes| H[DET: write cell context — issue only + allow paths]
  H --> I([leave: cell ready])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,D,E,G,H det
```

## Notes

- **Reuse fidelity.** ready-for-agent: *Fresh worktree, install, headless agent*. Worktree jest obowiązkowy — nie „cwd głównego klona”.
- **Izolacja.** Jeden ticket = jeden worktree = jeden branch. Brak dirty conflicts między misjami; idle cleanup po merge/skip.
- **Kontekst wąski.** Agent w następnym podgrafie czyta **tylko** issue + dozwolone pliki/ścieżki z Allowed actions — nie cały świat i nie czat historii.
- **Install jest DET.** `npm i` / `poetry install` / Makefile — skrypt z repo; fail = stop, nie „agent naprawi środowisko na ślepo”.
- **Occupancy.** Cell żyje do PR open / skip / teardown; równoległy drugi claim na to samo repo → defer w label-start.
- **Handoff contract.** Output = `{worktree_path, branch, base_sha, issue_payload, allow_paths[]}` albo `{ok:false, reason:install|worktree}`.
