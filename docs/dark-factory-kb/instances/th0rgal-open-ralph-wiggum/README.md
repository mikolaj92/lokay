<!-- spine: spine_agent_loop -->
# Open Ralph Wiggum

**Repo:** [Th0rgal/open-ralph-wiggum](https://github.com/Th0rgal/open-ralph-wiggum) · ★1885 · TypeScript (Bun) · MIT · CLI `ralph`

## Co to jest

Open-source implementacja techniki Ralph: **ten sam prompt** podawany w pętli agentowi (Claude Code, Codex, Copilot, Cursor Agent, Qwen Code, OpenCode) aż promise / max iterations. CLI-only (bez pluginu Stop-hook Claude). `--tasks`, `--status`, `--add-context` mid-loop. Autor promuje też [sandboxed.sh](https://github.com/Th0rgal/sandboxed.sh) jako izolację Linux per task.

## Graf

```mermaid
flowchart TD
  P["Prompt / prompt file"] --> R["ralph \"…\" --agent …"]
  R --> A[Agent CLI iteracja N]
  A --> FS[Pliki + git history]
  FS --> Check{promise / max-iter?}
  Check -->|nie| Hint["opcjonalnie --add-context"]
  Hint --> A
  Check -->|tak| Done[Stop]
  Stat["ralph --status"] -.-> R
```

## Co / gdzie / jak

| Warstwa | Mechanizm |
|---------|-----------|
| **Trigger** | `ralph "prompt"` lub plik promptu; `--tasks` |
| **Stan** | Kod na dysku + git (świeży kontekst, stary kod) |
| **Role** | Jedna pętla; brak wbudowanego reviewera |
| **Sandbox** | Zewnętrzne (sandboxed.sh); nie worktree fleet w core |
| **Testy** | W promptcie / agent sam odpala |
| **Merge / PR** | Brak natywnego label→PR — to silnik pętli, nie mill forge |

Lżejszy kuzyn Ralphy / Ralph Orchestrator: czysta pętla, multi-agent switch.

## Confidence

**80 / 100** — klarowny OSS Ralph CLI, aktywny; nie jest ticket mill (trzeba dołożyć kolejkę/PR samemu).

## Linki

- https://github.com/Th0rgal/open-ralph-wiggum
- https://ghuntley.com/ralph/
- https://github.com/Th0rgal/sandboxed.sh
