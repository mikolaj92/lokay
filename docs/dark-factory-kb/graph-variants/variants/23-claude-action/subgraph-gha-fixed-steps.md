# Subgraph: gha-fixed-steps

**Theme:** stały YAML GHA = deterministyczny kręgosłup; kroki nie są wybierane przez LLM.  
**Mode mix:** 100% DET. Claude Action jest *wywoływany*, nie orkiestruje jobów.

## Flow

```mermaid
flowchart TD
  A([enter: matched event]) --> B[DET: job if-guard already true]
  B --> C[DET: permissions block min]
  C --> D[DET: actions/checkout fetch-depth 0]
  D --> E{occupancy: claude/issue-N exists?}
  E -->|live conflict| F[DET: comment defer + exit]
  F --> Z0([leave: defer])
  E -->|free| G[DET: wire secrets ANTHROPIC_API_KEY / OAuth]
  G --> H[DET: set prompt + claude_args from template]
  H --> I[DET: uses anthropics/claude-code-action@v1]
  I --> J([yield: claude-leaf])
  J -->|leaf result| K{ok artifact?}
  K -->|fail| Z1([leave: fail receipt])
  K -->|branch / comment| L([leave: artifact ready])

  classDef det fill:#1a3a2a,stroke:#3d8f6a,color:#e8fff3
  classDef bad fill:#3a1a1a,stroke:#c05050,color:#ffe8e8
  class B,C,D,E,F,G,H,I,K det
  class Z0,Z1 bad
```

## Fixed step table (compose)

| # | Step | Who | Notes |
|---|------|-----|-------|
| 1 | `if:` label / `@claude` | DET | już z label-event |
| 2 | `permissions:` least privilege | DET | contents/PRs/issues write tylko gdy issue→PR |
| 3 | `actions/checkout@v4` | DET | świeża komórka runnera = worktree |
| 4 | secret / OIDC wire | DET | never in prompt body |
| 5 | `claude-code-action@v1` | invoke leaf | prompt template stały |
| 6 | post: receipt / defer comment | DET | fail closed |

## Notes

- **YAML is the program.** Kolejność kroków jest stała — jak Temporal Workflow body / label-FSM spine. Model nie dopisuje `steps:`.
- **Runner = fresh cell.** Efekt fresh worktree z ready-for-agent: czysty checkout per run, K=1 na ticket.
- **Prompt = template, nie router.** `prompt:` / `claude_args:` są wypełniane z issue payload; nie „zdecyduj co robić w fabryce”.
- **Permissions cynic.** Review-only → read + PR write. Issue→PR → contents + pull-requests write. Bez zbędnego `id-token` jeśli nie Bedrock/Vertex.
- **Handoff.** Yield claude-leaf = `{issue_id, workspace, prompt_ref, branch_target: claude/issue-N}`.
