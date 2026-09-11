# Subgraph: label-event

**Theme:** etykieta / `@claude` / event = jedyny start (reuse Claude Code Action triggers).  
**Mode mix:** 100% DET. Agent nie wybiera pracy.

## Flow

```mermaid
flowchart TD
  A([enter: GitHub webhook]) --> B{event type?}
  B -->|issues.labeled| C[DET: read label.name]
  B -->|issue_comment.created| D[DET: contains @claude?]
  B -->|workflow_dispatch| E[DET: require issue_number input]
  B -->|other| Z0([leave: ignore])
  C --> F{label in allowlist?}
  F -->|no| Z0
  F -->|yes ready-for-agent / claude / do| G[DET: bind issue payload]
  D -->|no| Z0
  D -->|yes| G
  E -->|missing| Z0
  E -->|ok| G
  G --> H{authorship / allowlist?}
  H -->|fail closed| Z1([leave: deny + receipt])
  H -->|ok| I[DET: claim token + issue_id]
  I --> J([leave: matched — handoff GHA])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class C,D,E,F,G,H,I det
  class Z0,Z1 bad
```

## Notes

- **Reuse fidelity.** Claude Code Action aktywuje się z kontekstu workflow: label, mention `@claude`, assignment, albo explicit `prompt` w automation mode — nie z „agent przeszukał backlog”.
- **Allowlist etykiet.** Typowo `ready-for-agent` (KLEPACZ) albo `claude` / `do` (plan-then-do). Poza listą = ignore.
- **Fail closed.** Brak matcha → idle. Nie wymyślaj ticketów, nie bierz unlabeled „bo wygląda na gotowe”.
- **K=1 hint.** Handoff niesie jeden `issue_id`; occupancy (otwarty `claude/issue-N` / live run) może zablokować claim w następnym podgrafie.
- **Handoff contract.** Output = `{issue_id, title, body, labels, trigger, actor}` albo `{ignore|deny}`.
