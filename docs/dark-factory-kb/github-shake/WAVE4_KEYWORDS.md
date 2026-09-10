# WAVE4 — marketing / keyword GitHub sweep

Sweep date: 2026-09-10 (PT / Europe/Warsaw). Keywords: `software factory`, `AI engineer`, `autonomous PR`, `lights out`, `dark factory`, `coding agents fleet`, `multi-agent software`, `self-healing codebase`, `AI SDLC`.

**Honesty scale (one line):**
- **real mill** — code owns loop: queue/state machine, isolated workers, deterministic gates, PR/merge path, retries/escalation
- **assisted IDE** — skills/prompt packs/IDE scaffold; human still drives session (or merge is always human)
- **vapor** — README buzzwords, agent-count theater, no inspectable orchestration / dogfood / E2E

Stars ≈ snapshot at sweep; not a quality signal.

---

## Keyword: `software factory`

| Repo | ★ | Honesty |
|------|---|---------|
| [fabro-sh/fabro](https://github.com/fabro-sh/fabro) | ~1.6k | **real mill** — DOT workflow graphs, sandboxes (Daytona), git checkpoints, API/UI; „dark factory” branding but HITL gates honest |
| [Runfusion/Fusion](https://github.com/Runfusion/Fusion) | ~1.2k | **real mill** (early) — multi-agent orchestrator + worktrees + dashboard; marketing loud („to production automatically”) but mechanisms named |
| [vercel-labs/eve-software-factory-template](https://github.com/vercel-labs/eve-software-factory-template) | ~1.1k | **real mill** — Foreman 4 stations (classify→plan→implement→review) on eve; draft PR + human merge; Vercel product substrate |
| [strongdm/attractor](https://github.com/strongdm/attractor) | ~1.3k | **assisted IDE / spec** — NLSpecs only; you prompt an agent to *build* Attractor; no runtime mill in-repo |
| [disler/super-simple-software-factory](https://github.com/disler/super-simple-software-factory) | ~820 | **real mill** (minimal) — Python ADW owns graph; agents = bounded nodes; SQLite trace; explicitly *no* merge/sandbox yet |
| [owainlewis/machinist](https://github.com/owainlewis/machinist) | ~400 | **real mill** (infra) — Go control plane: named commands, local creds, PR handoff; human merge; early-access |
| [coleam00/ai-software-factory](https://github.com/coleam00/ai-software-factory) | ~215 | **real mill** (WIP) — issue→Archon SDLC→merge story; README admits E2E still needs live run / upstream branch |
| [addyosmani/factory](https://github.com/addyosmani/factory) | ~180 | **real mill** (policy) — charter + GitHub labels + Claude routines; no custom orchestrator; humans merge; gates.sh + independent verifier |
| [dmitriy-yefremov/software-factory](https://github.com/dmitriy-yefremov/software-factory) | (template) | **real mill** — GH label state machine, 4 Claude agents, CI-gate, auto-merger + `needs-attention`; fork-and-own |
| [mastra-ai/softwarefactory-template](https://github.com/mastra-ai/softwarefactory-template) | ~40 | **real mill** — Factory Server: issues→plans→impl→reviewed PRs; platform optional |
| [ashtilawat/minimum-viable-factory](https://github.com/ashtilawat/minimum-viable-factory) | ~40 | **real mill** — Linear webhook→stages + 3 human gates→deploy greenfield; ~700 LOC readable |
| [gethuman-sh/human](https://github.com/gethuman-sh/human) | ~65 | **assisted IDE → mill kit** — secure sandbox + connectors + lifecycle skills; autonomy optional dial, not lights-out |
| [finna/Finn-loop](https://github.com/finna/Finn-loop) | ~300 | **assisted IDE** — 3 Claude skills (spec/build/review); label `agent-ready`; **humans merge** by design |
| [Leeroo-AI/kapso](https://github.com/Leeroo-AI/kapso) | ~100 | **real mill** (adjacent) — self-improving factory for *measurable* ML/algo objectives (MLE/ALE/RelBench), not general product SDLC |
| [konflux-ci/konflux-ci](https://github.com/konflux-ci/konflux-ci) | ~180 | **real mill** (legacy CI) — cloud-native *build* factory (trusted artifacts); not AI coding agents |
| [redhat-cip/software-factory](https://github.com/redhat-cip/software-factory) | ~40 | **real mill** (legacy CI) — pre-LLM software factory platform; keyword collision |

**Buzz to watch:** „software factory” alone hits DoD/FedRAMP CI packs and Konflux — filter with agent/PR/worktree language.

---

## Keyword: `dark factory` / `lights out`

| Repo | ★ | Honesty |
|------|---|---------|
| [peter-stratton/dark-factory](https://github.com/peter-stratton/dark-factory) | (see OSS note) | **real mill** — `godark`: implementer + 2 reviewers, Docker sandbox, squash-merge or `needs-human-review`; dogfood claim |
| [0-sayed/dark-factory](https://github.com/0-sayed/dark-factory) | (see OSS note) | **real mill** — Archon workflows + Agent Orchestrator + worktree-compose; bootstrap PR human, then parallel tasks |
| [simonasrazm/simon-factory-lights-out](https://github.com/simonasrazm/simon-factory-lights-out) | ~25 | **assisted IDE / protocol** — gated pipeline *protocol* for agents; thin vs full runtime |
| [elasticclaw/elasticclaw](https://github.com/elasticclaw/elasticclaw) | ~40 | **real mill** — control plane: issue events→sandbox→scoped GH App creds→PR→CI→cleanup (OpenClaw workers) |
| [harperaa/agentic-secure-dark-factory](https://github.com/harperaa/agentic-secure-dark-factory) | ~2 | **assisted / template** — security-first lights-out *story*; verify runtime depth before trust |
| [jleechanorg/dark-factory](https://github.com/jleechanorg/dark-factory) | ~8 | **real mill** (narrow) — Attractor-pattern DOT pipeline runner (Python) |
| [marius-patrik/DarkFactory](https://github.com/marius-patrik/DarkFactory) | ~2 | **assisted / template** — turn-key governed pipeline template; multi-harness claims need smoke-test |
| Name-squat flood (`OneDro1d/dark-factory`, `dark-factory-build/…`, demos, skills forks) | 0–1 | **vapor** — empty/teaching/demo; keyword land-grab after meme spread |
| MindStudio blog „What Is a Dark Factory AI Agent” | n/a | **vapor (content)** — definitional SEO; no repo mill |

**Note:** `lights out` alone is polluted (webcam LED, Discord themes, AMSI tools, puzzle games). Pair with `factory` / `agent` / `SFLO`.

---

## Keyword: `autonomous PR` / autonomous merge

| Repo | ★ | Honesty |
|------|---|---------|
| [miniforge-ai/miniforge](https://github.com/miniforge-ai/miniforge) | (emerging) | **real mill** — nested loops + policy gates + PR monitor; dogfood „530+ PRs”; Clojure-centric alpha |
| [dmitriy-yefremov/software-factory](https://github.com/dmitriy-yefremov/software-factory) | — | **real mill** — auto-merger behind CI + reviewer + guardrails |
| [peter-stratton/dark-factory](https://github.com/peter-stratton/dark-factory) | — | **real mill** — squash-merge on dual review pass |
| [coleam00/ai-software-factory](https://github.com/coleam00/ai-software-factory) | ~215 | **real mill** (WIP) — merge path via Archon; honesty about unfinished E2E |
| Most „autonomous PR” GH search hits | — | **noise** — generic `agent` repos (AgentGPT, trading agents, phone agents); ignore without factory/SDLC context |

**Honesty tell:** real mills name *who merges* (bot vs human), *what blocks merge* (CI, independent reviewer, charter), and *escalation label*. Vague „ships without anyone reading the diff” without gates = marketing.

---

## Keyword: `AI SDLC` / `autonomous SDLC`

| Repo | ★ | Honesty |
|------|---|---------|
| [ai-sdlc-framework/ai-sdlc](https://github.com/ai-sdlc-framework/ai-sdlc) | ~280 | **real mill** — DoR gate, worktree orchestrator, cross-harness reviewers, DSSE; autonomous flag still `experimental` |
| [asklokesh/loki-mode](https://github.com/asklokesh/loki-mode) | ~1.0k | **real mill** — CLI/SDK with verified completion gates; commercial Autonomi wrapper; greenfield-strong |
| [bitbitcodes/autonomous-sdlc](https://github.com/bitbitcodes/autonomous-sdlc) | ~37 | **assisted IDE** — scaffolds **52 agent prompts** into `.sdlc/`; no independent runtime — IDE chat is the orchestrator |
| [potpie-ai/potpie](https://github.com/potpie-ai/potpie) | ~5.7k | **assisted IDE / substrate** — context graph for agents (code+history+workflows); not a merge mill by itself |
| [ai-driven-dev/framework](https://github.com/ai-driven-dev/framework) | ~460 | **assisted IDE** — plugins/skills/hooks marketplace for AI-driven dev |
| [pangon/ai-sdlc-framework](https://github.com/pangon/ai-sdlc-framework) | ~130 | **assisted IDE** — process framework focused on *pre-coding* phases |
| [bashebr/ai-native-sdlc](https://github.com/bashebr/ai-native-sdlc) | ~44 | **assisted IDE** — skill/plugin of Anthropic AI-Native SDLC with human gates |
| [GoogleCloudPlatform/smart-sdlc](https://github.com/GoogleCloudPlatform/smart-sdlc) | ~90 | **assisted / samples** — GCP tooling patterns across SDLC |
| [aws-samples/sample-ai-powered-sdlc-patterns-with-aws](https://github.com/aws-samples/sample-ai-powered-sdlc-patterns-with-aws) | ~90 | **assisted / samples** — Bedrock/Kiro pattern gallery |
| Zero-★ `Autonomous-SDLC*` student forks | 0 | **vapor** — course scaffolds, empty READMEs |

---

## Keyword: `coding agents fleet` / `multi-agent software`

| Repo | ★ | Honesty |
|------|---|---------|
| [os-factory/har](https://github.com/os-factory/har) | ~90 | **real mill** (harness) — worktree isolation + verify + Mission Control; „one agent or a fleet” is literal |
| [RenseiAI/donmai-libraries](https://github.com/RenseiAI/donmai-libraries) | ~65 | **unclear / watch** — „multi-agent fleet management” claim; inspect libs vs vapor dashboard |
| [fabro-sh/fabro](https://github.com/fabro-sh/fabro) | ~1.6k | **real mill** — concurrent workflow runs / cloud sandboxes = fleet ops |
| [Runfusion/Fusion](https://github.com/Runfusion/Fusion) | ~1.2k | **real mill** — multi-node agents, kanban board as fleet UI |
| MetaGPT / ChatDev class (see `oss/`) | high | **assisted / research mill** — multi-agent *roles* in one process; often demo-app, not GitHub merge factory |
| „52 AI agents” scaffolds | — | **assisted / vapor-adjacent** — agent *count* ≠ mill; check for queue+sandbox+gates |

---

## Keyword: `self-healing codebase`

| Repo | ★ | Honesty |
|------|---|---------|
| Almost all GH hits (`SHCE`, `CodeHealer-GPT5`, `HydraOps`, …) | 0–1 | **vapor** — portfolio/course titles; no sustained dogfood or gate machinery |
| Factory inner loops (miniforge repair, Fabro fix loops, Foreman red-CI fix) | — | **real mill** *behavior* — self-heal as *bounded retry on gate fail*, not magic SRE product |
| Kapso / ML self-improve loops | — | **real mill** (domain-specific) — heal/improve against score, not „heal any codebase” |

**Buzz tell:** „flawlessly self-heals codebases in sandboxes” + 0 stars + no CI = skip.

---

## Keyword: `AI engineer`

Too broad for factory discovery (job titles, courses, AgentGPT clones). Useful only when co-occurring with factory/dark/SDLC/PR/worktree. No separate table — treat as noise filter.

---

## Buzzwords that *hide* real mechanisms (cheat sheet)

| README phrase | Often means (if honest) | Red flag if missing |
|---------------|-------------------------|---------------------|
| dark / lights-out factory | unattended loop + escalation | no state machine / no who-merges |
| software factory | queue + stages + evidence | just a chat UI or skill pack |
| autonomous PR | bot opens/merges under gates | „merge” with only LLM approve |
| multi-agent / fleet | parallel worktrees or sandboxes | N prompt files, one human session |
| self-healing | retry on test/CI fail | claims SRE without monitors |
| AI SDLC | DoR + orchestrator + review harness | 12 „phase agents” as markdown only |
| 52 agents | prompt library | no runtime orchestrator |
| NLSpec / „implement this repo” | spec-as-source (Attractor) | stars without runnable code |

---

## Shortlist — highest signal real mills (this wave)

1. **fabro-sh/fabro** — graph mill + sandboxes  
2. **peter-stratton/dark-factory** — Claude+GH dark loop with adversarial reviewers  
3. **0-sayed/dark-factory** — Archon+AO parallel factory  
4. **miniforge-ai/miniforge** — governed loops + dogfood PRs  
5. **vercel-labs/eve-software-factory-template** — productized 4-station factory  
6. **ai-sdlc-framework/ai-sdlc** — decision engine + attestations  
7. **disler/super-simple-software-factory** — clearest „code owns the loop” pedagogy  
8. **addyosmani/factory** — charter/label mill without custom daemon  
9. **elasticclaw/elasticclaw** — issue→sandbox→PR control plane  
10. **dmitriy-yefremov/software-factory** — label-SM + auto-merge template  

## Shortlist — assisted IDE (useful, not dark)

- **finna/Finn-loop**, **bitbitcodes/autonomous-sdlc**, **gethuman-sh/human**, **potpie-ai/potpie**, **strongdm/attractor** (spec), **bashebr/ai-native-sdlc**

## Shortlist — vapor / skip

- Keyword-squat `dark-factory` empties; `self-healing codebase` 0★ agents; generic `AI engineer` / AgentGPT-class hits; lights-out games/malware tools.

---

## Polish (skrót)

Hasła marketingowe **dark factory / software factory / AI SDLC** od 2025–2026 pokrywają prawdziwe młyny (graf/kolejka/gate/PR) *oraz* puste skille i squat nazw. Filtr: **czy kod (nie prompt) trzyma pętlę**, czy jest **izolacja (worktree/sandbox)**, **deterministyczny gate**, i **jasne kto merguje**. „52 agentów” i „self-healing codebase” bez gwiazd = prawie zawsze vapor. Najczystszy dydaktycznie mechanizm w tej fali: *Agent proposes, code disposes* (Disler SSSF).

