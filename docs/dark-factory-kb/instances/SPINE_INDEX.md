# Spine index — who decides the next step

Generated 2026-09-10 (Europe/Warsaw). All `instances/*/README.md` except `_*`.

| Spine | Meaning |
|-------|---------|
| `spine_deterministic` | Fixed graph / FSM / Actions / DOT / Temporal / scripts decide next step; LLM only in leaf nodes |
| `spine_agent_loop` | Agent decides next actions; continuous executor / free tool loop is the orchestrator |
| `spine_hybrid` | Unclear or mixed D-spine + free-agent orchestration |

**Counts:** deterministic=60 · agent_loop=28 · hybrid=9 · **total=97**

| slug | spine | confidence_spine | why |
|------|-------|------------------|-----|
| [a20185-overnightagent](./a20185-overnightagent/) | `spine_agent_loop` | 80 | Supervisor queues tasks; free agent adapters + fix-loop in worktrees |
| [a7t-ai-three-body-agent](./a7t-ai-three-body-agent/) | `spine_deterministic` | 88 | Cron GHA + gh/jq scripts decide Implementer/Fixer/Merger; Claude leaf |
| [ableinc-coding-agent-loop](./ableinc-coding-agent-loop/) | `spine_deterministic` | 85 | Fixed label FSM; harness owns claim/worktree/tests/PR; LLM only plan/impl |
| [addyosmani-factory](./addyosmani-factory/) | `spine_deterministic` | 82 | factory:* label FSM + gates.sh + scheduled routines; agents fill slots |
| [agentlane-agent-ready](./agentlane-agent-ready/) | `spine_deterministic` | 90 | Pure DoR lint Action/CLI; no coding agent — gate only |
| [ai-sdlc-framework-ai-sdlc](./ai-sdlc-framework-ai-sdlc/) | `spine_deterministic` | 78 | cli-orchestrator tick walks dependency graph; subagents are leaves |
| [aignermax-autonomous-issue-agent](./aignermax-autonomous-issue-agent/) | `spine_agent_loop` | 75 | Daemon + Claude headless Worker/Reviewer free sessions; thin label FSM |
| [amazon-q-developer](./amazon-q-developer/) | `spine_agent_loop` | 82 | Product is continuous Q development-agent session; label/comment triggers |
| [anthropics-claude-code-action](./anthropics-claude-code-action/) | `spine_deterministic` | 88 | Label/event → fixed GHA action steps; Claude Code is leaf |
| [arikwaisman-klaus](./arikwaisman-klaus/) | `spine_deterministic` | 81 | klaus run on .dot; runtime fixed graph (sprint-plan may emit DOT) |
| [artushin-conductor-ai](./artushin-conductor-ai/) | `spine_deterministic` | 80 | .wf DSL workflow engine owns steps/gates; Claude in tmux slots |
| [ashtilawat-minimum-viable-factory](./ashtilawat-minimum-viable-factory/) | `spine_deterministic` | 78 | LangGraph fixed PM→Arch→Dev→Review→Deploy with human gates |
| [az9713-attractor-software-factory](./az9713-attractor-software-factory/) | `spine_deterministic` | 83 | PipelineRunner walks blueprint.dot; LLM fills nodes |
| [berenddeboer-ready-for-agent](./berenddeboer-ready-for-agent/) | `spine_agent_loop` | 95 | Canonical ready-for-agent: thin harness + headless agent implement/review/PR |
| [bitbitcodes-autonomous-sdlc](./bitbitcodes-autonomous-sdlc/) | `spine_agent_loop` | 55 | IDE-chat sdlc.orchestrator + markdown agents; no fixed ticket runner spine |
| [brevity1swos-holdout](./brevity1swos-holdout/) | `spine_deterministic` | 84 | Holdout sealed oracle; grading = exit codes/JSON not LLM-judge |
| [bytedance-deer-flow](./bytedance-deer-flow/) | `spine_hybrid` | 84 | DET GitHub webhook fan-out/UUID5/fire_and_forget; coding = free agent+gh in sandbox |
| [campallison-attractor](./campallison-attractor/) | `spine_deterministic` | 86 | Go DOT parser+pipeline runner; agent loop is leaf under DOT |
| [chippingway-orchestrator](./chippingway-orchestrator/) | `spine_deterministic` | 85 | workflow:* label + pinned JSON FSM; orchestrator advances stages |
| [codebuddy-npc](./codebuddy-npc/) | `spine_agent_loop` | 70 | CNB NPC autonomous plan→code→PR; free tool loop drives delivery |
| [coder-tasks](./coder-tasks/) | `spine_deterministic` | 80 | coder label → create-task Action → fixed Coder Task path |
| [codoop-flow](./codoop-flow/) | `spine_deterministic` | 82 | codoop-execute CLI owns claim/worktree/verify gates; agent only builds |
| [cursor-cloud-agents](./cursor-cloud-agents/) | `spine_agent_loop` | 90 | Temporal durability around continuous agent loop as work orchestrator |
| [dagent](./dagent/) | `spine_deterministic` | 88 | Explicit TypeScript DAG watchdog; LLM only in specialist nodes |
| [darkshade9-prismconductor](./darkshade9-prismconductor/) | `spine_hybrid` | 65 | Kanban column FSM plus free execute agents and self-heal — mixed |
| [dmitriy-yefremov-software-factory](./dmitriy-yefremov-software-factory/) | `spine_deterministic` | 88 | GitHub label-swap FSM + GHA scripts drive planner→…→auto-merge |
| [dryvist-ai-workflows](./dryvist-ai-workflows/) | `spine_deterministic` | 85 | Reusable GHA workflow_call; ai:ready → fixed resolver/assign steps |
| [dubsopenhub-dark-factory](./dubsopenhub-dark-factory/) | `spine_deterministic` | 88 | Fixed phases 0→PR + sealed-envelope Shadow Score grading |
| [elasticclaw](./elasticclaw/) | `spine_deterministic` | 88 | Control-plane workflow YAML stages; OpenClaw agents are sandbox leaves |
| [eugeneorlov-noxdev](./eugeneorlov-noxdev/) | `spine_agent_loop` | 82 | TASKS.md queue + free Claude Code session in Docker worktree |
| [fabro-sh-fabro](./fabro-sh-fabro/) | `spine_deterministic` | 90 | DOT/workflow graph decides next node; agents only in sandbox leaves |
| [finn-loop](./finn-loop/) | `spine_agent_loop` | 78 | Claude Code /loop skills; free build/review agent sessions |
| [forge-sdlc-forge](./forge-sdlc-forge/) | `spine_deterministic` | 82 | LangGraph typed stations; agent does not route between stages |
| [gabrielkoerich-orchestrator](./gabrielkoerich-orchestrator/) | `spine_hybrid` | 72 | Label poll + LLM router picks agent/model, then free tmux agent |
| [github-copilot-coding-agent](./github-copilot-coding-agent/) | `spine_agent_loop` | 88 | Ephemeral Actions host free explore→edit→test coding-agent loop |
| [google-jules](./google-jules/) | `spine_agent_loop` | 85 | Async session agent on GCP VM owns edit/bash/tests |
| [guild-software-factory](./guild-software-factory/) | `spine_deterministic` | 80 | Fixed dispatcher→planner→implementer→reviewer pipeline |
| [harryaskham-caravan](./harryaskham-caravan/) | `spine_deterministic` | 76 | Typed merge-queue decision tree; agent only on typed repair leaf |
| [hsubra89-brrr](./hsubra89-brrr/) | `spine_agent_loop` | 88 | Ralph-loop Rust CLI; continuous implement/review agent-agnostic |
| [inngest-step-functions](./inngest-step-functions/) | `spine_deterministic` | 84 | Event+step.run durable steps; LLM inside one step, not graph router |
| [jawhnycooke-attractor](./jawhnycooke-attractor/) | `spine_deterministic` | 80 | attractor run *.dot; conditions route fix-loop without LLM orchestrator |
| [jbs-agentic-fix](./jbs-agentic-fix/) | `spine_deterministic` | 85 | agentic-fix label → fixed GHA Prepare/Fix/Verify/Submit |
| [jeffma8888-agent-foundry](./jeffma8888-agent-foundry/) | `spine_deterministic` | 78 | foundry.config + fixed PM→Engineer→Reviewer→Tester→Release stages |
| [jeromeetienne-issue-autofix](./jeromeetienne-issue-autofix/) | `spine_agent_loop` | 78 | Claude plugin overnight free /issue_autofix; thin autofix label FSM |
| [jessekaff-trismegistus](./jessekaff-trismegistus/) | `spine_agent_loop` | 85 | Daemon polls tasks.md; free Claude skip-permissions per task |
| [jhostalek-junior](./jhostalek-junior/) | `spine_agent_loop` | 88 | Overnight daemon spawns free Claude Code in isolated worktrees |
| [jhugman-attractor-pi-dev](./jhugman-attractor-pi-dev/) | `spine_deterministic` | 88 | attractor-pi run workflow.dot; examples are fixed DOT graphs |
| [jmccarthy-attractor-c](./jmccarthy-attractor-c/) | `spine_deterministic` | 82 | C11 attractor pipeline.dot runner; graph is code |
| [jnurre64-sandbox-pal-action](./jnurre64-sandbox-pal-action/) | `spine_deterministic` | 90 | Label-driven GHA FSM triage→plan→TDD→review→PR |
| [jp-explaza-ai-implement](./jp-explaza-ai-implement/) | `spine_deterministic` | 88 | Asana/n8n → ai-implement label → claude-code-action fixed path |
| [jp-label-auto-fix](./jp-label-auto-fix/) | `spine_deterministic` | 90 | Label→GHA→worktree→claude→PR; label FSM owns stages |
| [kkipngenokoech-phoenix](./kkipngenokoech-phoenix/) | `spine_deterministic` | 82 | Watcher label state machine Planner→Coder→Tester→PR |
| [knot0-com-dagain](./knot0-com-dagain/) | `spine_deterministic` | 85 | SQLite DAG executor owns plan/execute/verify; agents are runners |
| [kr-leesumok-plug-and-play](./kr-leesumok-plug-and-play/) | `spine_deterministic` | 88 | Fork GHA: code-gen label → claude-code-action → PR |
| [lennystepn-hue-issue2claude](./lennystepn-hue-issue2claude/) | `spine_deterministic` | 85 | Marketplace Action: claude-ready → fixed issue/fix/rebase modes |
| [linear-agent](./linear-agent/) | `spine_agent_loop` | 88 | Tracker-native coding session; Claude/Codex free tool loop |
| [luminik-io-alfred](./luminik-io-alfred/) | `spine_deterministic` | 80 | Fixed plan→approve→build→review→fix→ship; merge_gate.py predicate |
| [mastra-softwarefactory-template](./mastra-softwarefactory-template/) | `spine_hybrid` | 70 | Staged intake/triage/plan/review gates mixed with free sandbox build |
| [michaelshimeles-ralphy](./michaelshimeles-ralphy/) | `spine_agent_loop` | 95 | Ralph Wiggum continuous agent loop / worktree fleet |
| [microsoft-conductor](./microsoft-conductor/) | `spine_deterministic` | 92 | YAML+Jinja routes 0-token orchestration; type:agent is leaf |
| [mikeyobrien-ralph-orchestrator](./mikeyobrien-ralph-orchestrator/) | `spine_agent_loop` | 92 | Hat/event loop keeps agent running until LOOP_COMPLETE |
| [miniforge](./miniforge/) | `spine_hybrid` | 75 | DAG executor + nested agent loops + meta-agents — mixed |
| [nilbuild-claude-queue](./nilbuild-claude-queue/) | `spine_agent_loop` | 80 | Batch CLI: free Claude Code per issue until solved/failed |
| [okeyamy-forge](./okeyamy-forge/) | `spine_agent_loop` | 85 | SWE-agent think→act→observe loop in Docker watch |
| [open-policy-agent-conftest](./open-policy-agent-conftest/) | `spine_deterministic` | 93 | OPA/Conftest Rego merge gate; zero LLM in verdict |
| [openautocoder-agentless](./openautocoder-agentless/) | `spine_deterministic` | 95 | Agentless fixed localize→repair→validate; zero ReAct tool-loop |
| [openfactory-core](./openfactory-core/) | `spine_deterministic` | 85 | Temporal-ish state machine + adapters; agents are pluggable leaves |
| [os-factory-har](./os-factory-har/) | `spine_deterministic` | 78 | Fixed Discover→Isolate→Build→Verify→Handoff harness stages |
| [peter-stratton-dark-factory](./peter-stratton-dark-factory/) | `spine_agent_loop` | 90 | godark: Claude Code mill; implementer/reviewer free sessions |
| [plain-python-go-fsm](./plain-python-go-fsm/) | `spine_deterministic` | 88 | Enum+transition table in code; agent functions are activities |
| [point-labs-dev-arc](./point-labs-dev-arc/) | `spine_deterministic` | 90 | Effect.ts engine walks convergence.dot; no imperative orchestration |
| [prefect-pydantic-spine](./prefect-pydantic-spine/) | `spine_deterministic` | 86 | Prefect @flow/@task owns control; Pydantic Agent.run is leaf task |
| [prnvh-plancompiler](./prnvh-plancompiler/) | `spine_deterministic` | 94 | One LLM plan call → validate → compile Python; no further LLM |
| [qoder-ai-employees](./qoder-ai-employees/) | `spine_hybrid` | 72 | GHA event router wakes autonomous Waker agents — mixed |
| [ramp-inspect](./ramp-inspect/) | `spine_agent_loop` | 90 | OpenCode continuous background agent in Modal sandbox |
| [robotsix-mill](./robotsix-mill/) | `spine_deterministic` | 80 | SQLite board columns = FSM refine→implement→deliver→merge |
| [salehaiftikharr-agent-forge](./salehaiftikharr-agent-forge/) | `spine_agent_loop` | 78 | Minion free implement loop until prove-then-PR verify gate |
| [samueljklee-attractor](./samueljklee-attractor/) | `spine_deterministic` | 92 | Python DOT engine; LLM fills box/codergen leaves only |
| [sandcastle-afk](./sandcastle-afk/) | `spine_agent_loop` | 92 | sandcastle.run iteration loop to COMPLETE is the orchestrator |
| [shbhmydv-grindstone](./shbhmydv-grindstone/) | `spine_deterministic` | 85 | State machine disposes epochs; done_when gate; agents are workers |
| [shep-ai-shep](./shep-ai-shep/) | `spine_agent_loop` | 85 | Daemon spawns free agent CLI in worktrees; CI-fix re-invokes agent |
| [shipshitdev-skills](./shipshitdev-skills/) | `spine_deterministic` | 82 | dispatch:* label → fixed GHA claim→TDD→qa→PR |
| [sortie-ai-sortie](./sortie-ai-sortie/) | `spine_agent_loop` | 92 | Poll+workspace+agent adapter continuous executor; hooks after_run |
| [stoneforge-ai](./stoneforge-ai/) | `spine_hybrid` | 70 | Director LLM plans + free workers + steward auto-merge — mixed |
| [stripe-minions](./stripe-minions/) | `spine_hybrid` | 90 | Blueprint SM with agent nodes + deterministic hydrate/lint/push |
| [tasksmd-tasks-md](./tasksmd-tasks-md/) | `spine_agent_loop` | 80 | /next-task agent-loop queue layer; agent is the engine |
| [temporal-workflow-spine](./temporal-workflow-spine/) | `spine_deterministic` | 94 | Temporal Workflow (CODE) + LLM only in Activities; replay-safe spine |
| [tgoodwin-tractor](./tgoodwin-tractor/) | `spine_deterministic` | 84 | tractor reap *.dot runner; agent CLI as leaf via ACP |
| [th0rgal-open-ralph-wiggum](./th0rgal-open-ralph-wiggum/) | `spine_agent_loop` | 92 | Pure Ralph same-prompt continuous agent loop CLI |
| [thecraighewitt-agent-pipeline](./thecraighewitt-agent-pipeline/) | `spine_deterministic` | 86 | Pure GHA/bash FSM label→agent slot→review≤3→promote |
| [thegpvc-gp-foundry](./thegpvc-gp-foundry/) | `spine_deterministic` | 95 | harness.dot → GHA; DOT graph is deterministic spine |
| [trigger-dev-tasks](./trigger-dev-tasks/) | `spine_deterministic` | 83 | Trigger.dev task graph/checkpoints; agent turn inside task |
| [uber-cadence-spine](./uber-cadence-spine/) | `spine_deterministic` | 82 | Cadence Workflow/Activity same deterministic contract as Temporal |
| [uber-software-factory](./uber-software-factory/) | `spine_hybrid` | 75 | Platform building blocks + managed Minion agents; workflows mixed |
| [vsavkin-polygraph-factory](./vsavkin-polygraph-factory/) | `spine_deterministic` | 78 | Essay recipe: thin script wiring capabilities; factory = workflow |
| [windmill-flow-spine](./windmill-flow-spine/) | `spine_deterministic` | 80 | Windmill flow edges/scripts/approval=CODE; AI Agent step=LLM leaf |
| [witify-firstmate](./witify-firstmate/) | `spine_deterministic` | 88 | Harness owns Linear/git/PR side-effects; claude -p only code leaf |

## Strict heuristics

- **Usually agent_loop:** ready-for-agent, godark, sortie, ralphy/Ralph family, overnight Claude daemons, commercial coding-agent sessions (Cursor/Jules/Copilot/Q/Linear/Ramp).
- **Usually deterministic:** gp-foundry / Attractor DOT, Agentless, Temporal/Cadence/Conductor/Prefect/Inngest/Trigger/Windmill spines, label→fixed GHA steps, harness-owned side-effects with LLM leaves, OPA/holdout gates.
- Each README starts with `<!-- spine: spine_* -->`.

