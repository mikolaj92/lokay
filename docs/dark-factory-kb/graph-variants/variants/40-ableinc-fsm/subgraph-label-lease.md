# Subgraph: label-lease

**Theme:** stała etykieta `agent-ready` + **SQLite lease** (1 issue / repo); harness owns claim.  
**Mode mix:** 100% DET. Zero AGENT w kręgosłupie.

## Flow

```mermaid
flowchart TD
  A([enter: discovery poll / label agent-ready]) --> B[DET: list open issues with agent-ready]
  B --> C{exclude_repos / allowlist OK?}
  C -->|no| Z0([leave: ignore])
  C -->|yes| D{SQLite lease free for repo?}
  D -->|held by other| Z1([leave: defer])
  D -->|free| E[DET: acquire lease 1 issue/repo]
  E --> F[DET: bind issue_id + repo to lease row]
  F --> G[DET: audit log / receipt]
  G --> H([leave: handoff worktree-plan])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,C,D,E,F,G det
  class Z0,Z1 bad
```

## Transition table (compose AbleInc)

| From | Event / predicate | To | Who |
|------|-------------------|----|-----|
| *(human)* | label `agent-ready` | claim candidate | człowiek |
| unlabeled / excluded | discovery tick | ignore | harness |
| `agent-ready` + lease free | acquire SQLite | claimed → worktree-plan | harness |
| `agent-ready` + lease held | defer | stay ready | harness |
| claimed done / fail | release lease | free for next | harness |

## Notes

- **Fixed label FSM.** Impulse = tylko `agent-ready`. Harness nie inventuje nowych stage-labels z LLM.
- **Lease = mutex.** SQLite cache: max 1 aktywne issue na repo. SoT procesu nadal na GitHub (labele/komentarze).
- **Agent never claims.** Plan/Implement nie wołają discovery ani `gh issue list`.
- **Handoff contract.** `{issue_id, repo, lease_id}` albo `{ignore|defer}`.
