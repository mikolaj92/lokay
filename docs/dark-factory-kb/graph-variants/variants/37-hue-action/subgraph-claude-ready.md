# Subgraph: claude-ready

**Theme:** etykieta `claude-ready` / tokeny komentarza = jedyny start + DET route do stałego `mode:`.  
**Mode mix:** 100% DET. Agent nie wybiera pracy ani trybu (`issue` / `fix` / `rebase`).

## Flow

```mermaid
flowchart TD
  A([enter: GitHub webhook]) --> B{event type?}
  B -->|issues.labeled| C[DET: label.name == claude-ready?]
  B -->|issue_comment.created| D{issue vs PR?}
  B -->|other| Z0([leave: ignore])
  C -->|no| Z0
  C -->|yes| E[DET: bind issue payload]
  D -->|plain issue| F{body has claude-retry or /claude?}
  D -->|pull_request thread| G{body token?}
  F -->|no| Z0
  F -->|claude-retry / slash| E
  G -->|claude-fix| H[DET: route mode=fix]
  G -->|claude-rebase| I[DET: route mode=rebase]
  G -->|else| Z0
  E --> J{author_association allowlist?}
  H --> J
  I --> J
  J -->|OWNER/MEMBER/COLLABORATOR fail| Z1([leave: deny + receipt])
  J -->|ok + issue path| K([leave: handoff mode-issue])
  J -->|ok + fix route| L([leave: handoff mode-fix])
  J -->|ok + rebase route| M([leave: handoff mode-rebase])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class C,D,E,F,G,J det
  class Z0,Z1 bad
```

## Notes

- **Reuse fidelity.** Issue2Claude aktywuje się z `claude-ready`, `claude-retry`, `claude-fix`, `claude-rebase` (oraz slash `/claude …`) — nie z „agent przeszukał backlog”.
- **Mode route = DET.** Ten sam podgraf tylko *klasyfikuje event* na stały job `mode:`; model nigdy nie wybiera `issue` vs `fix` vs `rebase`.
- **Allowlist association.** Workflow dogfood wymaga OWNER / MEMBER / COLLABORATOR na komentarzach — fail closed poza listą.
- **K=1 hint.** Handoff niesie jeden `issue_id` / `pr_number`; occupancy (live run na tym samym ticket) może zablokować claim w jobie.
- **Handoff contract.** `{issue_id|pr_number, trigger, mode: issue|fix|rebase, actor}` albo `{ignore|deny}`.
