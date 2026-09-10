# WAVE1 — Dark factory / coding mill repos (GitHub shake)

Zebrane **2026-09-10** (UTC+2). Źródła: WebSearch + `gh search repos` / `gh api`.

**Count: 28 real mill repos** (poniżej). Osobno: edge / early / nie-mill — na końcu.

Skala determinizmu: **D** = deterministyczna orkiestracja (state machine / DOT / cron / DAG), **A** = agent-heavy (LLM decyduje routing/role), **mixed** = D-spine + A-nodes.

---

## Tier A — dosłownie dark / issue→PR mills

### 1. fabro-sh/fabro
- **URL:** https://github.com/fabro-sh/fabro
- **Stars:** 1583 · Rust · MIT
- **Archetype:** `dot-graph` · `harness-cli` · `control-plane`
- **Det vs agent:** **mixed** (D: Graphviz DOT + human gates; A: agent nodes w sandboksach)
- **Mechanizm:** „Dark software factory for expert engineers”. Pipeline = wersjonowany graf DOT (branching, loops, parallelism, hexagon human gates). Style CSS-like routują modele per node; cloud sandboxes (Daytona); git checkpoint per stage; fix loops na fail testów; REST + UI. Single binary Rust. Cel: odłączyć człowieka od babysittingu, zostawić go przy gate’ach procesu.

### 2. Agent-Field/SWE-AF
- **URL:** https://github.com/Agent-Field/SWE-AF
- **Stars:** 993 · Go/Python · Apache-2.0
- **Archetype:** `fleet` · `issue-to-pr`
- **Det vs agent:** **mixed** (control stack plan/exec/governance; A: role agents)
- **Mechanizm:** „Autonomous engineering fleet” na AgentField. Jedno API call → PM → architect → tech lead → sprint planner → issue writer → coder (worktree) → QA → reviewer → synthesizer (FIX/APPROVE/BLOCK) → advisor/replanner → merger. Multi-model per role; fleet-scale parallel builds; inner retry + outer replan. Fabryka, nie single-agent wrapper.

### 3. HenryLach/taskplane
- **URL:** https://github.com/HenryLach/taskplane
- **Stars:** 214 · TypeScript
- **Archetype:** `fleet` · `issue-to-pr`
- **Det vs agent:** **mixed** (świadomie „light-factory”: transparent orchestration)
- **Mechanizm:** Multi-agent coding orchestration z wysoką obserwowalnością. Blisko mills, ale marketingowo light (człowiek widzi przebieg) — wartościowy kontrast do lights-out.

### 4. coleam00/dark-factory-experiment
- **URL:** https://github.com/coleam00/dark-factory-experiment
- **Stars:** 151 · Python
- **Archetype:** `issue-to-pr` · `holdout-judge`
- **Det vs agent:** **mixed** (D: bash cron + GitHub labels as state machine; A: Archon→Claude Code nodes)
- **Mechanizm:** Live Level-4 factory: ludzie piszą issues / promują release; triage→implement→validate-PR→auto-merge na cronie. GitHub labels = FSM. Validator holdout (nie czyta planu implementacji). Governance files (`MISSION.md`, `FACTORY_RULES.md`) niedotykalne. Dispatcher celowo bez LLM.

### 5. akashgit/remote-factory (re:factory)
- **URL:** https://github.com/akashgit/remote-factory
- **Stars:** 69 · Python
- **Archetype:** `evolution` · `self-improve` · `fleet`
- **Det vs agent:** **A-heavy** z score gate (D: keep-if-better)
- **Mechanizm:** CEO + Researcher/Strategist/Builder/Reviewer/Evaluator/Archivist jako Claude Code (lub Codex/Bob) subprocesses. Każda zmiana = hipoteza scorowana przed/po; meta mode (ACE) poprawia agentów. Plugin Claude Code + GHA rebuild. Fork/linia: też `RobotSail/remote-factory` (0★, ten sam koncept).

### 6. foundatron/octopusgarden
- **URL:** https://github.com/foundatron/octopusgarden
- **Stars:** 61 · Go
- **Archetype:** `holdout-judge` · `evolution`
- **Det vs agent:** **mixed** (D: attractor loop; A: codegen + LLM judge)
- **Mechanizm:** Spec (md) + scenarios (YAML holdout). Attractor: generate → Docker run → validator → LLM judge 0–100 → feedback; wonder/reflect przy stall. Brak PR review w pętli — „code as opaque weights”. Wzorzec StrongDM software factory.

### 7. miniforge-ai/miniforge
- **URL:** https://github.com/miniforge-ai/miniforge
- **Stars:** 42 · Clojure
- **Archetype:** `issue-to-pr` · `fleet`
- **Det vs agent:** **mixed** (D: DAG executor + policy packs; A: nested agent loops)
- **Mechanizm:** „Factory not chatbot”. 4 zagnieżdżone pętle: team agents → inner quality gates → post-delivery monitor → meta-agents (progress, test quality, conflicts, resources). Task graph + isolated worktrees + budgets. Plan→code→test→self-review→PR.

### 8. elasticclaw/elasticclaw
- **URL:** https://github.com/elasticclaw/elasticclaw
- **Stars:** 40 · Go · Apache-2.0
- **Archetype:** `control-plane` · `issue-to-pr`
- **Det vs agent:** **D-spine** (workflows/triggers); A = OpenClaw workers w sandbox
- **Mechanizm:** Control plane dark factories: Linear/GH/Shortcut/webhook → workspace+workflow → sandbox (Daytona/CMX/exe.dev) → scoped GitHub App creds → agent (OpenClaw) → PR → CI/review lifecycle → cleanup. Single-binary server + UI.

### 9. DUBSOpenHub/dark-factory
- **URL:** https://github.com/DUBSOpenHub/dark-factory
- **Stars:** 25 · TypeScript/Markdown (Copilot CLI skill)
- **Archetype:** `holdout-judge` · `protocol` · `harness-cli`
- **Det vs agent:** **mixed** (8 specialist agents, różne model families; sealed-envelope suite)
- **Mechanizm:** Copilot CLI skill: goal → disposable worktree → multi-agent pipeline → PR. Sealed-envelope / Shadow Score: builder nigdy nie widzi hidden acceptance suite. Model independence (różne rodziny modeli na build vs judge).

### 10. simonasrazm/simon-factory-lights-out (SFLO)
- **URL:** https://github.com/simonasrazm/simon-factory-lights-out
- **Stars:** 25 · Python
- **Archetype:** `protocol` · `issue-to-pr`
- **Det vs agent:** **mixed** (D: gated pipeline.yaml + artifact validators; A: Scout+specialist agents)
- **Mechanizm:** 5 gates, każde z wymaganym artifactem — no skip. Scout matchuje agentów po `BRIEF.md`/`SOUL.md`. Parallel QA+security na gate 3. `.sflo/` per factory run. Cursor skill `/sflo`.

### 11. peter-stratton/dark-factory (`godark`)
- **URL:** https://github.com/peter-stratton/dark-factory · docs: https://godarkfactory.com
- **Stars:** 23 · Go
- **Archetype:** `harness-cli` · `issue-to-pr`
- **Det vs agent:** **mixed** (D: 10-step pipeline + `godark vet`; A: implementer + 2 reviewers)
- **Mechanizm:** Claude Code CLI. Milestone issues → implementer (sandbox Docker) → quality reviewer (read-only) → functional reviewer → squash-merge lub `needs-human-review`. Architecture-as-code. Repo budowane własnym `godark run`.

### 12. numman-ali/openfactory
- **URL:** https://github.com/numman-ali/openfactory
- **Stars:** 18 · TypeScript
- **Archetype:** `fleet` · `issue-to-pr`
- **Det vs agent:** **mixed**
- **Mechanizm:** AI-native SDLC orchestration: Refinery (PRD) → Foundry (arch) → Planner (work orders + MCP do IDE agents) → Validator; knowledge graph; self-hosted LLM path.

### 13. missingstudio/eva
- **URL:** https://github.com/missingstudio/eva
- **Stars:** 15 · Bun/TS · MIT
- **Archetype:** `harness-cli` · `protocol`
- **Det vs agent:** **D-leaning** (plugin kernel + declared Workflow; early — agent loop jeszcze w roadmap)
- **Mechanizm:** OSS autonomous software factory scaffold: jeden harness/contract/trace/verifier/bill. CLI + service. Early: dziś workflow/plugin kernel, pełny agent mill w drodze.

### 14. BayramAnnakov/factory-agent
- **URL:** https://github.com/BayramAnnakov/factory-agent
- **Stars:** 7 · TypeScript (~700 LOC)
- **Archetype:** `issue-to-pr`
- **Det vs agent:** **A-heavy** (jeden Managed Agent session)
- **Mechanizm:** Linear webhook → Claude Managed Agents sandbox → clone → implement + Puppeteer evidence → GH PR; status stream do Linear. Minimal mill „ticket in, PR out”.

### 15. PotLock/zerobuild
- **URL:** https://github.com/PotLock/zerobuild
- **Stars:** 6 · Rust (ZeroClaw runtime)
- **Archetype:** `fleet`
- **Det vs agent:** **A-heavy** (hierarchical CEO + specialists)
- **Mechanizm:** Idea → Orchestrator (CEO) spawn BA/UI/Dev/Tester/DevOps → deploy-ready. Factory mode vs single-agent. GitHub OAuth connector. Greenfield factory bardziej niż mill po istniejącym backlogu.

### 16. Open-Factory-Digital/openfactory-core
- **URL:** https://github.com/Open-Factory-Digital/openfactory-core
- **Stars:** 4 · Python · Apache-2.0
- **Archetype:** `issue-to-pr` · `control-plane`
- **Det vs agent:** **D-spine** (Temporal + state machine); A = pluggable coding agents
- **Mechanizm:** Tickets → size → `box prove` → plan → agent (Claude/Codex/Kimi/OpenCode) → your tests → independent reviewer (inny silnik) → merge policy. Adapter axes: tracker/board/forge/CI/agent/sandbox. Panel UI. Honest STATUS.md.

### 17. Tanush1912/ouroboros
- **URL:** https://github.com/Tanush1912/ouroboros
- **Stars:** 4 · Python
- **Archetype:** `self-improve` · `issue-to-pr`
- **Det vs agent:** **mixed** (D: state machine `determine_next_*`; A: plan/implement/test/review; typed Pydantic contracts)
- **Mechanizm:** Agent-first factory: NL task → merged PR. Typed handoffs (nie regex). AST lint arch constraints. Self-referential: agenci poprawiają infrastrukturę agentów tym samym PR process.

### 18. ede-bzh/architekt-factory-platform
- **URL:** https://github.com/ede-bzh/architekt-factory-platform
- **Stars:** 4 · Python
- **Archetype:** `fleet`
- **Det vs agent:** **A-heavy** (163 agents / 41 workflows claimed)
- **Mechanizm:** Internal studio engine: SAFe-aligned multi-agent lifecycle, TDD, SAST, Playwright, MCP tool surface. Skala „digital product studio”, nie mały mill.

### 19. 0-sayed/dark-factory
- **URL:** https://github.com/0-sayed/dark-factory
- **Stars:** 3 · JavaScript
- **Archetype:** `issue-to-pr` · `harness-cli`
- **Det vs agent:** **mixed**
- **Mechanizm:** Codex + Archon + Agent Orchestrator. Bootstrap ręczny, potem autonomia. Mały sibling konceptu coleam00/Archon dark factory.

### 20. thegpvc/gp-foundry
- **URL:** https://github.com/thegpvc/gp-foundry
- **Stars:** 1 · TypeScript
- **Archetype:** `dot-graph` · `issue-to-pr`
- **Det vs agent:** **D-spine** (DOT → GitHub Actions)
- **Mechanizm:** Compile DOT graph → GHA pipeline: scout→builder→reviewer→fixer→merge_gate; self-heal cron. Issues in, reviewed auto-merged PRs out. Blisko Fabro, ale GH Actions jako runtime.

### 21. damien-robotsix/robotsix-mill
- **URL:** https://github.com/damien-robotsix/robotsix-mill
- **Stars:** 1 · Python
- **Archetype:** `sqlite-mill` · `issue-to-pr`
- **Det vs agent:** **mixed** (D: SQLite queue + stages; A: containerized LLM agents; human gate po refine)
- **Mechanizm:** Ticket → refine → **human approve** → implement (Docker `--network none`) → deliver MR (GH/GitLab) → merge when CI green. Orchestrator = mill (bez webhook/scheduler forge). Textbook small-team mill.

### 22. ntholm86/evo-releases (evo)
- **URL:** https://github.com/ntholm86/evo-releases
- **Stars:** 1 · Python packages
- **Archetype:** `self-improve` · `evolution`
- **Det vs agent:** **mixed** (D: closed pipeline phases; A: per-phase LLM)
- **Mechanizm:** Autonomous evolution engine: ANALYZE→DIAGNOSE→IMPLEMENT→VERIFY→DECIDE→RELEASE→EVOLVE. Fitness = merge rate; może ewoluować własny kod; hash-chained proof ledger. Binary releases; claimed self-release loop.

### 23. eLh0m3r0/Genesis-Factory
- **URL:** https://github.com/eLh0m3r0/Genesis-Factory
- **Stars:** 0 · Python
- **Archetype:** `fleet` · `self-improve`
- **Det vs agent:** **A-heavy** + D heartbeat
- **Mechanizm:** 24/7 machine: Claude Code + Telegram channels + Python heartbeat (no LLM) + Docker. Role: Product Analyst→PO→Architect→Dev(+Test worktrees)→QA (Playwright)→Security→DevOps auto-merge→Ops Monitor→Retrospective. Multi-project VISION.md.

### 24. kunalm2345/openfactory
- **URL:** https://github.com/kunalm2345/openfactory
- **Stars:** 0 · TypeScript
- **Archetype:** `issue-to-pr` · `holdout-judge`
- **Det vs agent:** **mixed**
- **Mechanizm:** Self-hosted: GH/Linear/Sentry issues → ascii.dev Box VMs. Triage/plan/build na factory box; verify = second agent + second VM (adversarial, inna rodzina modeli) → PR. SQLite settings; disposable VMs per issue.

### 25. rkaliupin/DAGent
- **URL:** https://github.com/rkaliupin/DAGent
- **Stars:** 0 · TypeScript
- **Archetype:** `issue-to-pr` · `dot-graph` (DAG)
- **Det vs agent:** **D-spine** (explicit DAG scheduler); A = specialist nodes; shell bypass na deploy
- **Mechanizm:** 12 agents / 4 phases DAG; self-heal; Playwright live-UI; „zero human until code review”. Cituje zbieżność ze Stripe Minions. Workflow types prune DAG. `.apm/` project config.

### 26. RobotSail/remote-factory
- **URL:** https://github.com/RobotSail/remote-factory
- **Stars:** 0
- **Archetype:** `evolution` · `self-improve`
- **Det vs agent:** **A-heavy** + score gate
- **Mechanizm:** Canonical description line of re:factory (CEO+6 specialists, ACE meta). Patrz też #5 akashgit (aktywniejszy fork/mirror z 69★).

### 27. davidegc1/GenesisFactory
- **URL:** https://github.com/davidegc1/GenesisFactory
- **Stars:** 1 · Python
- **Archetype:** `fleet`
- **Det vs agent:** **A-heavy**
- **Mechanizm:** Multi-agent orchestration „autonomously builds custom software” — mniejszy/early sibling Genesis line; mniej dokumentacji niż eLh0m3r0.

### 28. kherrera6219/theFactory
- **URL:** https://github.com/kherrera6219/theFactory
- **Stars:** 5
- **Archetype:** `fleet` · `protocol`
- **Det vs agent:** **mixed**
- **Mechanizm:** Local-first event-driven factory: task-activated specialists, multi-provider routing, isolated workspaces, runtime QC, audit evidence. „Not vibe coding.”

---

## Keyword hit map

| Keyword | Primary hits |
|---------|----------------|
| dark-factory / godark | peter-stratton, fabro, coleam00, DUBSOpenHub, 0-sayed, elasticclaw, octopusgarden |
| software factory | SWE-AF, zerobuild, OpenFactory*, eva, factory-agent, theFactory |
| ouroboros factory | Tanush1912/ouroboros |
| genesis factory | eLh0m3r0/Genesis-Factory, davidegc1/GenesisFactory |
| remote-factory | akashgit + RobotSail |
| evo self-improve | ntholm86/evo-releases |
| miniforge | miniforge-ai/miniforge |
| robotsix-mill | damien-robotsix/robotsix-mill |
| OpenFactory | numman-ali, Open-Factory-Digital, kunalm2345, deepelementlab (theory) |
| DAGent | rkaliupin/DAGent (mill); inne DAGent = libs — wykluczone |
| lights-out / SFLO | simonasrazm/simon-factory-lights-out |
| coding mill | robotsix-mill (+ komercyjne mills poza GH) |
| issue→PR agent | factory-agent, elasticclaw, gp-foundry, dark-factory* |
| recursive planner / self-driving | (Cursor blog — nie osobny OSS mill w tej fali; ouroboros/evo/remote-factory meta) |

---

## Edge / nie wliczone do 28 (noise lub nie-mill)

| Repo | Stars | Powód wykluczenia / edge |
|------|-------|--------------------------|
| deepelementlab/OpenFactory | 6 | Teoria/paradygmat, nie runtime mill |
| Extensible-AI/DAGent, RobotSe7en/dagent, cpgames/dagent | — | Framework/DAG lib lub desktop planner, nie factory |
| Demo-Smart-Factory…/OpenFactory, openfactoryio/* | — | Manufacturing / IoT |
| tdouce/remote_factory_girl | — | Test data factories |
| Lexaplus/KodingX / parsabarati/kodingx | — | Opis w search, repo 404 / niedostępne |
| wizicer/dark-factory, darkin100/talos | ≤5 | Eksperymenty cienkie / bez dojrzałego README mill |
| Red64llc/red64-cli, ikangai/factory, mikigraf/runmill | ≤5 | Early / thin — do WAVE2 |
| com-lihaoyi/mill etc. | high | False positive „mill” (build tools) |

---

## Skrót wniosków (PL)

1. **Najmocniejszy sygnał „dark factory” OSS:** Fabro (DOT harness), SWE-AF (fleet), coleam00 experiment (labels+Archon), peter-stratton/godark, robotsix-mill, Open-Factory-Digital.
2. **Holdout / sealed envelope** powtarza się (octopusgarden, coleam00, DUBSOpenHub, kunalm OpenFactory) — antidotum na reward hacking.
3. **Self-improve / ouroboros** = Tanush ouroboros, remote-factory ACE, evo, Genesis retrospective — osobna oś od issue→PR mill.
4. **Deterministyczny spine + agent nodes** dominuje nad „czystym multi-agent chat”; Fabro/gp-foundry/DAGent/OpenFactory-core/elasticclaw to ten wzorzec.
5. **KodingX** z keyword listy — niedostępne publicznie w momencie shake; trzymać na WAVE2 recheck.

