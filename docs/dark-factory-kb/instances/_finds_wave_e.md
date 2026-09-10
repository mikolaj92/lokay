# Wave E — finds log (marketplace / dispatch / focus list)

**Data:** 2026-09-10 (PT / Europe/Warsaw)  
**Filtr:** klepacz (ticket/spec/label → PR); skip slugów już w `instances/`.  
**Karty:** `instances/<slug>/README.md`  
**Focus brief:** marketplace Actions, `agentic-fix`, Solvio, JBS, phoenix forks, hue-issue2claude clones, shipshit, nilbuild, `dispatch:claude/codex`, autonomous-sdlc, ai-sdlc-framework, three-body-agent, agent-pipeline, Conductor, Grindstone, lindy, dagain.

## Już w KB (skip — nie duplikować)

| Slug | Brief hit |
|------|-----------|
| `shipshitdev-skills` | `dispatch:claude` / `dispatch:codex` marketplace skills |
| `nilbuild-claude-queue` | nilbuild batch CLI |
| `lennystepn-hue-issue2claude` | hue issue2claude Marketplace |
| `kkipngenokoech-phoenix` | phoenix (0 forks — brak sensownych forków do karty) |
| `berenddeboer-ready-for-agent` | related gate lineage |

## Karty napisane (10 NEW)

| Slug | ★ | Klepacz? | Confidence | Uwagi |
|------|---|----------|------------|-------|
| [a7t-ai-three-body-agent](a7t-ai-three-body-agent/) | 13 | tak — board→PR→merge | 86 | Najczystszy lights-out w fali |
| [jnurre64-sandbox-pal-action](jnurre64-sandbox-pal-action/) | 2 | tak — label FSM | 84 | agent-pipeline / claude-agent-dispatch |
| [ai-sdlc-framework-ai-sdlc](ai-sdlc-framework-ai-sdlc/) | 276 | tak — DoR→PR | 80 | Governance heavy |
| [agentlane-agent-ready](agentlane-agent-ready/) | 0 | gate — label `agent-ready` | 78 | Marketplace DoR front-door |
| [artushin-conductor-ai](artushin-conductor-ai/) | 0 | tak — `ticket-to-pr` | 76 | Local Conductor DSL |
| [shbhmydv-grindstone](shbhmydv-grindstone/) | 41 | job→done_when | 72 | Epoch SM; nie issue queue |
| [knot0-com-dagain](knot0-com-dagain/) | 10 | goal DAG→agents | 70 | Fresh-context DAG |
| [darkshade9-prismconductor](darkshade9-prismconductor/) | 0 | tak — issues kanban→PR | 68 | Desktop Conductor |
| [bitbitcodes-autonomous-sdlc](bitbitcodes-autonomous-sdlc/) | 37 | spec→SDLC (IDE) | 62 | 52 agents scaffold |
| [jbs-agentic-fix](jbs-agentic-fix/) | n/a blog | tak — `agentic-fix` | 58 | JP; brak public repo |

## Odrzucone / odłożone

| Kandydat | Powód |
|----------|--------|
| **Solvio** (zenn.dev/solvio `auto-fix`) | Dobry label→worktree→PR artykuł, ale brak OSS repo do forka; edukacyjny Solvio-ai ≠ mill |
| **Lindy** (lindy.ai GitHub) | SaaS Slack NL→GH actions; nie ticket mill OSS |
| **phoenix forks** | `kkipngenokoech/phoenix` forks_count=0 |
| **hue-issue2claude clones** | `gh search issue2claude` → tylko oryginał już w KB |
| **shipshit / nilbuild** dalsze | Już skartowane; brak nowego siblinga z czystym klepaczem |
| **ca-srg/maestro** | 404 / niedostępne w API |
| **latitude-dev/latitude-llm** | Observability + dispatch fix — za szerokie / ★4.6k |
| **github/gh-aw Agentic Workflows** | Platforma GH (preview); nie wąski obscure mill — odłóż na osobną falę |
| **win4r/team-tasks** | Linear/DAG/Debate modes — orchestration kit, nie GHA ticket mill |
| **Zeynep-Arikan/Solvio** | „Consulty AI” — nie coding mill |

## Preferencje jakości

1. **three-body-agent**, **sandbox-pal-action**, **ai-sdlc**, **agent-ready** — najwyższy stosunek realnej pętli ticket/PR.  
2. **Conductor** (artushin) + **PrismConductor** — lokalne board/ticket→PR.  
3. **Grindstone** / **dagain** — świetne SM/DAG; most issue→goal osobno.  
4. **JBS** — wzorzec `agentic-fix` do skopiowania, śledzić czy wypuszczą OSS.

## Metoda

`ls instances/` → skip; WebSearch + `gh api`/`gh search` + raw README. Cross-check WAVE4 keywords (nie dublować fabro/eve/addy już w KB).
