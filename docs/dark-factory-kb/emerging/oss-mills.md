# OSS mills & agent SDKs (factory substrates)

## OpenHands (All Hands / OpenHands Software Agent SDK)
- Production-oriented OSS coding agent; V1 SDK redesign (sandbox portability, REST/WS, multi-LLM, security analysis).  
- URLs: OpenHands docs / https://allhandsai.mintlify.app/sdk/arch/design ; MLSys 2026 SDK paper.  
- Role: Self-host Devin-class agent; Kubernetes enterprise path mentioned in roundups.

## robotsix-mill
- URL: https://github.com/damien-robotsix/robotsix-mill  
- SQLite management plane + file workspaces; event-driven workers; **containerized agents** (`--network none`, non-root, RO rootfs); stages: refine → **human approve** → implement → deliver MR → merge when CI green. Forge-agnostic until deliver (GitHub/GitLab).  
- Textbook small-team dark mill.

## DAGent
- URL: https://github.com/rkaliupin/DAGent  
- DAG of ~12 specialist agents; self-healing; browser tests; “zero human until code review”; cites convergence with Stripe Minions pattern (deterministic orchestration + project-specific agent config).

## OpenFactory
- URL: https://github.com/numman-ali/openfactory/  
- SDLC orchestration: Refinery (PRD) → Foundry (architecture) → Planner (work orders + MCP to IDE agents) → Validator; knowledge graph; self-hosted LLMs.

## theFactory
- URL: https://github.com/kherrera6219/theFactory  
- Local-first event-driven factory; task-activated specialist agents; isolated workspaces; ephemeral runtimes; audit evidence — “not vibe coding.”

## Related
- Aider / Cline / OpenCode / Goose — agent harnesses often *inside* mills (Ramp used OpenCode; Stripe forked goose).  
- Firecracker / gVisor / Kata — isolation layer if self-hosting sandboxes.

## Dark-factory distance
OSS stacks can implement full E if you bring queue + sandbox + merge policy. Highest leverage for teams that cannot send code to SaaS agents.

## Polish
OpenHands, robotsix-mill, DAGent, OpenFactory = otwarte substraty młynów (kolejka, sandbox, DAG agentów). Harnessy (goose/OpenCode) są silnikiem; fabryka to orkiestracja wokół nich.
