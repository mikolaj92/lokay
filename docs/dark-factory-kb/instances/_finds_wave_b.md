# Finds — wave B (local CLI/daemon harnesses)

Data: 2026-09-10 (Europe/Warsaw). Cel: **NEW** lokalne CLI/daemony issue→PR (npx, Go, Rust, Python). Wykluczone (już covered): `ready-for-agent`, `godark`, `gp-foundry`.

Keywords: issue to pr cli, coding agent harness, worktree agent loop, ralph loop, autonomous pr, label issue implement.

## Nowe karty (8)

| Slug | Stack | Trigger | Confidence | Repo |
|------|-------|---------|------------|------|
| [ableinc-coding-agent-loop](./ableinc-coding-agent-loop/) | Go daemon | label `agent-ready` + HITL `implement` | 88 | https://github.com/ableinc/coding-agent-loop |
| [sortie-ai-sortie](./sortie-ai-sortie/) | Go binary | `WORKFLOW.md` + `label:agent-ready` | 90 | https://github.com/sortie-ai/sortie |
| [shep-ai-shep](./shep-ai-shep/) | npx Node | `shep feat new` → worktree → draft PR | 86 | https://github.com/shep-ai/shep |
| [hsubra89-brrr](./hsubra89-brrr/) | Rust CLI | label `brrr` (GH/Linear) ralph loop | 84 | https://github.com/hsubra89/brrr |
| [witify-firstmate](./witify-firstmate/) | npx Node | Linear `ready-for-agent` | 82 | https://www.npmjs.com/package/witify-firstmate |
| [gabrielkoerich-orchestrator](./gabrielkoerich-orchestrator/) | brew/shell | GitHub `status:new` → tmux agent → PR | 87 | https://github.com/gabrielkoerich/orchestrator |
| [eugeneorlov-noxdev](./eugeneorlov-noxdev/) | Node CLI | `TASKS.md` overnight Docker loop | 80 | https://github.com/eugeneorlov/noxdev |
| [chippingway-orchestrator](./chippingway-orchestrator/) | Python/uv | `workflow:*` labels → PR → HITL | 89 | https://github.com/chippingway/orchestrator |

## Widziane, nie kartowane w tej fali (kolejka / overlap)

| Kandydat | Dlaczego odłożone |
|----------|-------------------|
| snarktank/ralph, jackemcpherson/ralph-cli, rickkdev/ralph | Metodologia/skrypt PRD→loop; słabszy natywny issue→PR niż brrr |
| VocanicZ/Harness | Fleet Claude Code + GitHub state machine — ciężki; partial overlap z shep/sortie |
| ComposioHQ/agent-orchestrator (ex AndreyChichurin) | Silny fleet (tmux/Docker/Linear); duży surface — kolejna fala |
| loop-engineer (npm) | Multi-role worktree orchestrator; mniej „label issue” |
| Kernel-Labs-AI/awt | Primitives worktree/handoff, nie pełny label-daemon |
| rjben/swarm-git | Parallel worktree merge mill; nie ticket-poll |

## Notatki metodologiczne

- Najczystsze klepacze label→PR: **coding-agent-loop**, **sortie**, **chippingway**, **brrr**, **firstmate**, **gabrielkoerich**.
- **Shep** / **noxdev** = harness lokalny PR-first / TASKS-first — nadal w scope „local CLI harness”, ale trigger ≠ etykieta GitHub.
- Wspólny wzorzec: harness własnie git/GitHub; agent w worktree; draft PR; merge Off lub HITL.
