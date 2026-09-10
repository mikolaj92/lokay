# Wave H — finds log (public writeups: internal klepacz mills)

**Data:** 2026-09-10 (~18:30 PT / Europe/Warsaw)  
**Cel:** karty z **publicznych** writeupów wewnętrznych / AFK mills — tylko jeśli jest **public repo** LUB **szczegółowa publiczna architektura** warta karty (link essays).  
**Lista GOAL:** Stripe Minions, Ramp Inspect, Uber Software Factory, Sandcastle/AFK, DEV.to agent-week stories.

## Karty napisane (6)

| Slug | Źródło | Repo? | Confidence | Uwagi |
|------|--------|-------|------------|-------|
| [stripe-minions](stripe-minions/) | Stripe.dev Part 1+2 + talk | nie (internal) | 92 | Devbox + Blueprints + Toolshed + goose fork; ~1300 PR/tydz. |
| [ramp-inspect](ramp-inspect/) | engineering.ramp.com spec | nie (OpenCode OSS harness) | 91 | Modal + CF DO + OpenCode; ~30%+ merged PR |
| [uber-software-factory](uber-software-factory/) | Uber blog + AI Eng talk + port | nie | 88 | 6 building blocks; Minion ≠ Stripe Minions |
| [sandcastle-afk](sandcastle-afk/) | mattpocock/sandcastle + AFK essay/YT | **tak** ★~7.9k | 93 | AFK loops; planner→impl→review→merge templates |
| [stoneforge-ai](stoneforge-ai/) | DEV.to + stoneforge-ai/stoneforge | **tak** ★~179 | 84 | DEV.to mill story z repo; auto-merge steward |
| [vsavkin-polygraph-factory](vsavkin-polygraph-factory/) | DEV.to / Medium Savkin | Polygraph produkt | 78 | Factory = workflow essay; nie OSS mill |

## Odrzucone / odłożone

| Kandydat | Powód |
|----------|-------|
| **Cloudflare Agents Week** (ADLC, Astro issue-zero factory) | „Agent week” ≠ DEV.to; ADLC = platforma CF, nie wąski ticket→PR klepacz; Astro dogfood warto kiedyś osobno |
| **StrongDM Attractor** | Już `emerging/attractor.md`; nlspec + factory StrongDM = bliżej L5 / nlspec niż ta fala GOAL |
| **Temporal Agents SDLC** (DEV.to aws-builders) | Szczegółowy eng post, ale orchestracja Temporal/Bedrock bez jasnego publicznego mill repo w GOAL |
| **Graflow / generic agent orchestration DEV.to** | Orkiestracja ogólna, nie ticket-to-PR mill |
| **Uber agent identity alone** | Wspomniane w karcie Uber; nie osobny mill |

## Preferencje jakości

1. **stripe-minions**, **ramp-inspect**, **sandcastle-afk** — najwyższy stosunek „realna architektura / marketing”.  
2. **uber-software-factory** — platform-first; klepacz siedzi na managed agents (Minion + loops).  
3. **stoneforge-ai** / **vsavkin-polygraph-factory** — DEV.to wave; Stoneforge = repo, Savkin = kanon „workflow not product”.

## Metoda

WebSearch + WebFetch oficjalnych blogów (Stripe, Ramp, Uber) + `gh`/raw GitHub (sandcastle, stoneforge) + DEV.to API markdown (vsavkin). Cross-check: nie mylić **Uber Minion** ze **Stripe Minions**.
