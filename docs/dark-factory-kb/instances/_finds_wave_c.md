# Wave C — finds (korporacyjne / produktowe ticket-to-PR)

**Data:** 2026-09-10 (Europe/Warsaw)  
**Cel:** nowe karty klepacz (nie L5) pod `instances/<slug>/` — Guild, Copilot coding agent, Linear Agent, Cursor cloud mill, Amazon Q, Jules, JP auto-fix, Coder Tasks.  
**Filtr:** issue/label/assign → sandbox → diff → PR; merge zwykle ludzki.

## Karty dodane

| Slug | Confidence | Trigger klepacza | Uwaga |
|------|------------|------------------|-------|
| [guild-software-factory](./guild-software-factory/) | 90 | `guild-auto` | Pipeline plan/impl/review + janitorzy; brak auto-merge; metryki własne Guild |
| [github-copilot-coding-agent](./github-copilot-coding-agent/) | 88 | assign / automations / `@copilot` | Actions env, hard 59m, 1 repo/PR |
| [linear-agent](./linear-agent/) | 87 | assign / triage automation / Slack | Tracker-native coding sessions + Diffs |
| [cursor-cloud-agents](./cursor-cloud-agents/) | 85 | Slack/GH/Linear/API (nie jedna etykieta) | Temporal mill; env = produkt; >40% PR wewnętrznie |
| [amazon-q-developer](./amazon-q-developer/) | 86 | label `Amazon Q development agent` / `/q dev` | Dev + osobny review agent |
| [google-jules](./google-jules/) | 84 | UI/CLI/API/GH label | Session FSM + `AUTO_CREATE_PR` |
| [jp-label-auto-fix](./jp-label-auto-fix/) | 82 | `auto-fix` / `agentic-fix` | DIY JP: Solvio Zenn + JBS blog; worktree + Claude Code |
| [coder-tasks](./coder-tasks/) | 80 | label `coder` → create-task-action | CDE mill; Tasks → ESR / Coder Agents |

## Świadomie pominięte / nie jako osobna karta Wave C

- **ready-for-agent / claude-code-action / godark / gp-foundry** — już w seed Alfred (`instances/`).
- **Devin / Factory.ai Missions / Sweep** — pokryte w `commercial/`; Wave C = lista GOAL użytkownika.
- **Coder Agents (następca Tasks)** — wspomniane w karcie `coder-tasks`; osobna karta gdy GA docs stabilniejsze.
- **L5 / app generators** (Bolt, v0) — poza klepaczem.

## Źródła szybkie

- Guild product + blog 2026-09-03; docs Smith blueprint  
- GitHub Copilot cloud agent docs + Coding agent 101  
- Linear „coding sessions” 2026-06-11  
- Cursor cloud-agent docs + lessons Jun 2026  
- AWS Q GitHub feature-development docs  
- Jules API types + Google Labs blog  
- Zenn solvio/63842f1417883a; JBS 2026-07-24 agentic-fix  
- Coder Tasks launch Dec 2025; create-task-action; docs Tasks/Agents deprecation

## Relacja do `commercial/` / `emerging/`

Karty `instances/` = **głębokie klepacz README** (mermaid + co/gdzie/jak + confidence). Notatki w `commercial/` i `emerging/` zostają jako szerszy kontekst archetypów — nie duplikować bez pogłębienia.
