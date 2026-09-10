<!-- spine: spine_hybrid -->
# gabrielkoerich/orchestrator

**Confidence: 87** — lokalny CLI/daemon (brew): GitHub Issue labels = stan; LLM router → worktree + tmux (claude/codex/opencode) → commit/PR `Closes #N`.

## Co to jest

Lekki autonomiczny orchestrator: zadania = GitHub Issues. Polluje `status:new`, router LLM wybiera agenta/model, tworzy izolowany worktree, odpala agenta w sesji tmux, zbiera JSON wynik, commit/push i otwiera PR. Opcjonalny agent-reviewer. Stan w labelach + sidecar JSON w `~/.orchestrator/`.

## Graf

```mermaid
flowchart TD
  iss[GitHub Issue status:new] --> route[LLM router: agent + profile]
  route --> wt[Worktree ~/.orchestrator/worktrees]
  wt --> tmux[tmux: claude / codex / opencode]
  tmux --> out[Parse agent JSON output]
  out --> push[Commit + push]
  push --> pr[PR Closes N]
  pr --> rev{Review agent?}
  rev -->|tak| grev[Drugi agent → GitHub review]
  rev -->|nie| human[status:needs_review / merge]
  grev --> human
```

## Co / gdzie / jak

| Element | Wartość |
|---------|---------|
| Stack | Shell + Python helpers; Homebrew formula; Just/yq/jq |
| Install | `brew tap gabrielkoerich/tap && brew install orchestrator` |
| Trigger | Label `status:new` (lub `orchestrator task add` / `orchestrator start` poll) |
| Sandbox | Bare clone + worktree per task; agent w tmux z pełnymi toolami |
| Agent | `claude`, `codex`, `opencode` (label `agent:*`) |
| Role | Labels: complexity, role:backend/frontend/docs, plan, no-agent |
| PR | Automatyczny; powiązanie `Closes #N` |
| Nie robi | Cloud control-plane — wszystko lokalnie w `~/.orchestrator/` |

## Linki

- https://github.com/gabrielkoerich/orchestrator
- (mirror/opis wcześniej jako orchestrator-sh)
