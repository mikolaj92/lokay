# ChatDev

**Nazwa EN:** ChatDev (OpenBMB)  
**Rola w dark factory:** **chat-chain** waterfall (design → code → test) przez role communicative agents; greenfield.

## Streszczenie (PL)

ChatDev (ACL 2024) to wirtualna firma software’owa: agenci (CEO, CTO, Programmer, Reviewer, Tester…) współpracują w **chat chain** — fazy rozbite na subtaski, multi-turn dialog. **Communicative dehallucination**: agent prosi o szczegóły zamiast halucynować. Natural language pomaga w designie; język programowania w debugowaniu. ChatDev **2.0 / DevAll** (2026) ewoluuje w zero-code multi-agent platform (YAML DAG, MCP/tools) — nie tylko SE. MacNet (DAG topologie, 1000+ agentów) jako zaawansowana topologia.

## Pipeline (kształt)

**Legacy software company:**
1. Demand / design phase (role biznesowe).  
2. Coding phase (programmer ↔ reviewer).  
3. Testing phase (tester ↔ programmer).  
4. Dokumentacja / warehouse artefaktów.

**ChatDev 2.0:** konfiguracja agentów + workflow YAML → scheduler → WareHouse/session.

## Narzędzia

- Chat chain orchestration.  
- 2.0: function/MCP tooling, memory, provider abstraction (OpenAI, Gemini…).  
- UI + FastAPI server.

## Testy

- Tester agent prowadzi dialogi debug; uruchamianie kodu w workspace.  
- Nie jest nastawiony na SWE-bench regression w legacy repo.

## Multi-agent

- **Tak — definiujące.** Role social + communicative patterns.  
- MacNet: topologie DAG zamiast łańcucha.

## Limity

- Greenfield / małe apki > enterprise monorepo issues.  
- Ryzyko niespójności między fazami mimo dehallucination.  
- Koszt dialogów.  
- 2.0 zmienia produkt — dokumentacja legacy vs DevAll.

## Repozytoria i paper’y

| Zasób | URL |
|-------|-----|
| GitHub | https://github.com/OpenBMB/ChatDev |
| arXiv | https://arxiv.org/abs/2307.07924 |
| ACL 2024 | https://aclanthology.org/2024.acl-long.810/ |
| MacNet arXiv | https://arxiv.org/abs/2406.07155 |
