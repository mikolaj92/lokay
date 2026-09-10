# MetaGPT vs ChatDev (skrót porównawczy)

Oba to multi-agent **„wirtualna software company”** nastawione głównie na **greenfield** (requirement → kod), nie na SWE-bench issue repair w legacy monorepo.

| | **MetaGPT** | **ChatDev** |
|--|-------------|-------------|
| Paper | ICLR 2024 | ACL 2024 |
| Orkiestracja | SOP + artefakty (PRD→design→tasks→code) | Chat chain + communicative dehallucination |
| Role | PM, Architect, ProjectManager, Engineer, QaEngineer | CEO/CTO/Programmer/Reviewer/Tester… |
| Testy | QaEngineer loop | Tester↔Programmer dialog |
| Ewolucja | FoundationAgents/MetaGPT | ChatDev 2.0 DevAll (YAML DAG, MCP) |
| Dark factory fit | Średni (brak legacy issue harness) | Średni (to samo) |

Szczegóły: [metagpt.md](./metagpt.md), [chatdev.md](./chatdev.md).

## URL

- https://github.com/FoundationAgents/MetaGPT
- https://github.com/OpenBMB/ChatDev
- https://arxiv.org/abs/2308.00352
- https://arxiv.org/abs/2307.07924
