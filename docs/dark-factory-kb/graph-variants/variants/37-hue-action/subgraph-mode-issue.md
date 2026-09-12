# Subgraph: mode-issue

**Theme:** stały job GHA `mode: issue` — implementacja issue → auto-review → otwarty PR.  
**Mode mix:** DET harness + AGENT leaf `lennystepn-hue/issue2claude` (`mode: issue`).

## Flow

```mermaid
flowchart TD
  A([enter: mode=issue claimed]) --> B[DET: permissions contents+PRs+issues write]
  B --> C[DET: actions/checkout fetch-depth 0]
  C --> D[DET: setup-node 22 + npm i -g claude-code]
  D --> E[DET: wire CLAUDE_CODE_OAUTH_TOKEN / API key + GITHUB_TOKEN]
  E --> F[AGENT: issue2claude mode=issue]
  F --> G[AGENT: indeks / kontekst repo]
  G --> H[AGENT SO: implement changes]
  H --> I[AGENT: auto-review second pass]
  I --> J{ok / clear scope?}
  J -->|underspecified / dangerous| K[DET: ask-or-stop comment]
  K --> Z0([leave: skip — no limbo])
  J -->|true| L[DET: open PR + summary Closes N]
  L --> M([leave: PR open — coder ceiling])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef agent fill:#3a2a1a,stroke:#c4893a,color:#fff6e8
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,C,D,E,K,L det
  class F,G,H,I agent
  class Z0 bad
```

## Fixed step table (compose)

| # | Step | Who | Notes |
|---|------|-----|-------|
| 1 | `if:` claude-ready / claude-retry | DET | z claude-ready subgraph |
| 2 | `permissions:` write trio | DET | contents / pull-requests / issues |
| 3 | `actions/checkout@v4` `fetch-depth: 0` | DET | świeża komórka = worktree |
| 4 | setup-node + `@anthropic-ai/claude-code` | DET | jak w ghostclip workflow |
| 5 | `issue2claude@main` `mode: issue` | AGENT leaf | implement + auto-review |
| 6 | open PR + summary | DET / action | coder ceiling; merge Off |

## Notes

- **YAML is the program.** `mode: issue` jest stałe w jobie — nie „zdecyduj tryb w promptcie”.
- **Auto-review = drugi pass w liściu.** Nadal AGENT entropy *wewnątrz* action; nie osobny orkiestrator merge.
- **Runner = fresh cell.** Efekt fresh worktree: czysty checkout per run, K=1 na ticket.
- **Meat ≡ AI.** To samo siedzenie: headless Claude w action albo człowiek-klepacz w tym samym runner contract.
- **Handoff contract.** `{pr_url, number, branch, summary}` \| `{skip, reason}`.
