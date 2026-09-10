# Wave G — finds log (EU / CN / JP / KR ticket→PR)

**Data:** 2026-09-10 (PT / Europe/Warsaw)  
**Cel:** MORE European / Chinese / JP / Korean klepacze **nie** obecne już w `instances/`. Hinty: Trae, Qoder, Kimi harness, CodeBuddy deeper, NeuroCOD, orkestr, Cerebe, JP auto-fix clones, Korean tools.  
**Filtr:** ticket/label/event → sandbox → diff → PR; skip vapor; merge zwykle ludzki.  
**Karty:** `instances/<slug>/README.md`

## Karty NEW (6) + pogłębienie (1)

| Slug | Geo | Klepacz? | Confidence | Uwagi |
|------|-----|----------|------------|-------|
| [qoder-ai-employees](qoder-ai-employees/) | CN (Alibaba) | tak — event Wakers→PR | 78 | QoderWake ≠ Quest/IDE; demo OSS ★1 |
| [codoop-flow](codoop-flow/) | CN-facing OSS | tak — pick→verify→PR | 72 | ★5; CLI guardrails + agent |
| [aignermax-autonomous-issue-agent](aignermax-autonomous-issue-agent/) | EU (Munich) | tak — `agent-task`→PR | 80 | Daemon multi-repo + Worker/Reviewer |
| [jeromeetienne-issue-autofix](jeromeetienne-issue-autofix/) | EU (France) | tak — `autofix` overnight | 76 | Claude Code plugin; never merges |
| [jp-explaza-ai-implement](jp-explaza-ai-implement/) | JP | tak — `ai-implement` + Asana/n8n | 84 | Klon poza Solvio/JBS; pilot 11/11 |
| [kr-leesumok-plug-and-play](kr-leesumok-plug-and-play/) | KR | tak — `code-gen` label | 58 | ★0 template; uczciwie cienki |
| [codebuddy-npc](codebuddy-npc/) *(update)* | CN | tak — @NPC→PR | 68↑55 | CNB docs events + npc/CodeBuddy |

## Odrzucone / vapor / nie-mill (nie karty)

| Kandydat | Powód |
|----------|--------|
| **Trae SOLO / Builder** (ByteDance) | AI-native IDE greenfield/iterate; brak publicznej kolejki ticket→PR |
| **Qoder Quest Mode** | Spec-driven IDE autonomy; mill = dopiero **QoderWake AI Employees** (karta wyżej) |
| **QoderAI/better-harness**, **trae-harness** | Meta-ewaluacja harnessów — wave D nadal aktualne |
| **Kimi Code / Moonshot kimi-code** | Coding CLI/agent-core; nie ticket mill / nie label FSM |
| **NeuroCOD** (neurocod.eu) | Marketing „10/10 AI Software Factory” + AI Act; brak OSS ticket→PR / dogfood; PL KRS istnieje ≠ produkt mill |
| **orkestr.eu** | EU sandboxe + Workers (proponują PR) — **substrat** E2B-like, nie kolejka klepacza |
| **Cerebe / momentiq-ai** | PRD→Blueprint + **quorum review gate** na commit/PR; nie wąski ticket queue mill |
| **orq.ai** | Agent lifecycle control plane — nie coding mill |
| **Autonoma** | Już odrzucone wave D (governance marketing) |
| **neokod Symphony** (kamo62) | Tracker→worktree→PR w kodzie, ale „not run E2E in production” — za wczesne |
| **TencentCloud/Octop** | Self-hosted assistant + ACP do CodeBuddy — runtime, nie mill |
| **HakjunMIN/SWE-agent** | Fork akademickiego SWE-agent (Seoul); nie oryginalny KR mill |
| **HakjunMIN github-mcp assign→SWE** | Glue MCP, nie samodzielny młyn |
| **gideokkim Claude GHA blog** | Dobry KR DIY opis; brak produktu/repo-mill do karty |
| **rariyama / Interpark Zenn** | Dodatkowe JP wzorce — wzmianka w karcie Explaza, nie osobne produkty |

## Preferencje jakości (ta fala)

1. **qoder-ai-employees**, **jp-explaza-ai-implement**, **aignermax-autonomous-issue-agent** — najwyższy stosunek „realny flow / marketing”.  
2. **codoop-flow**, **jeromeetienne-issue-autofix** — OSS wart śledzenia.  
3. **kr-leesumok** — placeholder KR; szukać mocniejszego KR produktu później.  
4. NeuroCOD / Cerebe / orkestr — trzymać na radarze governance/substrat, nie mylić z klepaczem.

## Metoda

WebSearch + WebFetch (Qoder docs, Zenn, CNB NPC, neurocod.eu) + `gh api` metadata (stars, location, README). Cross-check `instances/*` i `_finds_wave_d.md` (Trae/Qoder harness już rejected). CodeBuddy pogłębiony in-place, nie duplikat.
