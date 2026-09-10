# thegpvc/gp-foundry

- Repo: https://github.com/thegpvc/gp-foundry
- Idea: **graf DOT → skompilowane GitHub Actions**; GitHub = executor

## Teza

Zamiast stateful orkiestratora: skompiluj topologię do workflowów. Stan w labels/PR/reviews/cron.
Audytowalność > latencja hopów.

## Crew (software pack)

| Rola | Job |
|------|-----|
| scout | Triage issue → lane `build` / `plan` |
| planner | Plan read-only dla dużych issue |
| builder | Jedyny writer kodu → mały przetestowany PR |
| reviewer | Approve / request-changes |
| fixer | Bounded retry z reviewerem |
| janitor | Rebase `needs-rebase` |
| supervisor | Re-drive stranded; po 2 nudge → `needs-human` |
| retro | Lekcje → `.github/agents/memory/` |
| merge_gate | Polityka (nie persona): CI, size, paths → merge |

## Model

`harness.dot` → validate → model-check (bounded loops) → `.github/workflows/*.yml` (GENERATED).
Escape edge do `exit`/`needs_human` wymagany — checker odrzuca unbounded loops.

## Self-heal / self-improve

Janitor + supervisor + retro memory czytane przed pracą.

## Kontrast z daemonem (Lokay)

gp-foundry: zero hosta poza GitHubem. Lokay: lokalny daemon/LaunchAgent na mini.
Oba celują w issue→PR→merge; różnica = gdzie żyje graf.
