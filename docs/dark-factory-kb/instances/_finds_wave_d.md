# Wave D — finds log (obscure / non-US / low-star mills)

**Data:** 2026-09-10 (PT / Europe/Warsaw)  
**Filtr:** tylko kształt **klepacz** (ticket/spec/label → PR), nie L5 discovery i nie czysty chat/KG.  
**Karty:** `instances/<slug>/README.md`

## Karty napisane (10)

| Slug | ★ | Klepacz? | Confidence | Uwagi |
|------|---|----------|------------|-------|
| [robotsix-mill](robotsix-mill/) | 1 | tak — textbook | 88 | EU; SQLite mill; forge tylko deliver |
| [elasticclaw](elasticclaw/) | 40 | tak — control plane | 78 | Linear/GH → sandbox → PR |
| [miniforge](miniforge/) | 42 | tak — spec→PR+observe | 82 | Clojure dogfood 530+ PR |
| [dmitriy-yefremov-software-factory](dmitriy-yefremov-software-factory/) | 0 | tak — label FSM | 72 | auto-merge guardrails |
| [finn-loop](finn-loop/) | 306 | tak — `agent-ready` | 85 | humans merge; 3 skills |
| [dagent](dagent/) | 0 | tak — SPEC→tested PR | 68 | DAG Minions-like; Azure heavy |
| [openfactory-core](openfactory-core/) | 4 | tak — tickets→reviewed PRs | 74 | Open-Factory-Digital; ≠ manufacturing |
| [mastra-softwarefactory-template](mastra-softwarefactory-template/) | 39 | tak — gated issue→PR | 70 | UI factory; platform optional |
| [codebuddy-npc](codebuddy-npc/) | n/a SaaS | tak — CNB Issue→PR | 55 | Chiny; Trae/Qoder = nie mill |
| [ashtilawat-minimum-viable-factory](ashtilawat-minimum-viable-factory/) | 40 | części — greenfield | 58 | ticket→deploy; brownfield later |
| [addyosmani-factory](addyosmani-factory/) | 179 | tak — `factory:*` | 80 | reference; nie obscure |

## Odrzucone / odłożone (nie karty lub vapor)

| Kandydat | Powód |
|----------|--------|
| **potpie** (★5.7k) | Context graph + chat agents; PR tools istnieją, ale to nie wąski label→PR mill; za głośny |
| **Genesis-Factory** (★0) | L5: discovers what to build + Telegram + multi-project — poza klepaczem |
| **akashgit/remote-factory** (★69) | Evolution / hypothesis / keep-if-better; builder otwiera PR, ale nie kolejka ticketów |
| **Disler SSSF** (★821) | Superstrate ADW (code owns graph) — świetny wzorzec determinizmu, nie gotowy ticket mill; za popularny na „obscure” |
| **eve-software-factory-template** (★1116) | Idealny label `factory`→draft PR, ale Vercel-labs / nie obscure |
| **numman-ali/openfactory** (★18) | Refinery→Foundry→Planner work orders — bliżej SDLC studio niż klepacz issue |
| **autonoma** (EU) | Agentic testing + RIGOR governance marketing; BUILD claims bez jasnego OSS ticket→PR dogfood |
| **Qoder better-harness / Trae harness\*** | Meta-ewaluacja harnessów agentów, nie kolejka klepacza |
| **Fusion** | Brak jednoznacznego low-star ticket→PR hit w tej fali |
| **the-forever-loop/ouroboros** | Scout sam wybiera pracę (markdown handoffs) — agent wybiera, nie etykieta |
| **Q00/ouroboros** | Agent OS / Seed — warstwa runtime, nie mill |
| **evo** | Zbyt wieloznaczne; brak czystego mill hit |

## Preferencje jakości

1. **robotsix-mill**, **finn-loop**, **openfactory-core**, **elasticclaw**, **miniforge** — najwyższy stosunek „realna mrówka / marketing”.  
2. **dmitriy-yefremov**, **dagent** — warto śledzić mimo ★0.  
3. **codebuddy-npc** — jedyny solidny non-US/CN w fali; confidence niski z braku OSS.

## Metoda

WebSearch + `gh api` metadata + raw README fetch. Cross-check z `github-shake/WAVE1_MILLS.md` (nie duplikować bez pogłębienia — tu karty instance-level).
