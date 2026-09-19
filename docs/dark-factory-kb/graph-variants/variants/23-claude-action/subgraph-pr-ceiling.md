# Subgraph: pr-ceiling

**Theme:** coder ceiling = otwarty PR; merge zostaje przy DET policy / człowieku.  
**Mode mix:** DET open PR + policy; zero LLM-merge.

## Flow

```mermaid
flowchart TD
  A([enter: branch claude/issue-N]) --> B[DET: gh pr create Closes N]
  B --> C[DET: wait CI checks]
  C --> D{MergePolicy}
  D -->|Off default| E([leave: PR open — human])
  D -->|Always| F{CI green?}
  F -->|yes| G[DET: merge]
  F -->|no| E
  D -->|Classify| H{risk SO low + CI green?}
  H -->|yes| G
  H -->|no / high| E
  G --> I([leave: merged])
  E -->|review comments @claude| J([re-enter: label-event / leaf])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef stop fill:#2a1a1a,stroke:#a05050,color:#ffe8e8
  classDef ok fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  class B,C,D,F,G,H det
  class E stop
  class I ok
```

## Notes

- **Coder ≠ merge.** Claude Code Action (i GHA) kończą na PR. Gałka Off\|Classify\|Always jak w ready-for-agent; start **Off**.
- **Closes #N.** DET body PR linkuje issue; branch już `claude/issue-N`.
- **Classify SO (opc.).** Tylko gdy policy=Classify; advisory risk, nie autoryzacja sama w sobie. Off/Always → zero classify LLM.
- **Fail closed na czerwonym CI.** Always bez zielonego CI = hold.
- **Fix loop.** Komentarz / re-label / `@claude` wraca do label-event → GHA → leaf; nie merge z liścia.
- **NOT L5.** PR open przy Off = sukces klepacza; człowiek / QA trzyma merge i niewygodne pytania.
- **Handoff.** `{pr_url, number, policy_verdict: hold|merged}`.
