# jeromeetienne/issue_autofix — EU (Francja)

**Repo:** [jeromeetienne/issue_autofix](https://github.com/jeromeetienne/issue_autofix) · ★1 · Claude Code **plugin** · autor: Jerome Etienne (France)

## Co to jest

Nocny klepacz: kolejka Issues z label **`autofix`** → `/issue_autofix` w izolowanym worktree → najmniejsza poprawka → checks projektu → **jeden PR na issue** (`Fixes #N`). Nigdy nie merguje i nie zamyka Issues — rano człowiek przegląda. Opcjonalny `/issue_autofix_validate` → `autofix-ready` / `autofix-needs-info`.

## Graf

```mermaid
flowchart TD
  Q[Label autofix na Issue] --> Opt{Validate?}
  Opt -->|opcjonalnie| V[/issue_autofix_validate]
  V -->|vague| Info[autofix-needs-info — skip]
  V -->|ok| Ready[autofix-ready]
  Opt -->|skip| Run[/issue_autofix]
  Ready --> Run
  Run --> WT[worktree off main]
  WT --> Fix[Minimal fix + project checks]
  Fix -->|ok + no overlap| PR[gh pr create Fixes N]
  PR --> Done[Label autofixed]
  Fix -->|checks fail| Fail[Label autofix-failed]
```

## Co / gdzie / jak

| Warstwa | Mechanizm |
|---------|-----------|
| **Trigger** | Label `autofix` (+ ręczna komenda pluginu / overnight session) |
| **Stan** | Label FSM: `autofix` → `autofixed` \| `autofix-failed` (+ `autofix-ready` / `needs-info`) |
| **Role** | Single fixer; konflikt plików z innymi open autofix PR = reject |
| **Sandbox** | Isolated git worktree |
| **Testy** | „Project's own checks” jako gate przed PR |
| **Merge** | Wyłącznie człowiek rano |

Francuski OSS, kształt bliski JP `auto-fix` / `ready-for-agent`, ale jako **plugin Claude Code**, nie GHA.

## Confidence

**76 / 100** — README z pełnym FSM; ★1; zależny od Claude Code plugin ecosystem; nie vapor.

## Linki

- https://github.com/jeromeetienne/issue_autofix
