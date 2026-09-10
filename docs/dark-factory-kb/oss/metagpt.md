# MetaGPT

**Nazwa EN:** MetaGPT  
**Rola w dark factory:** multi-agent **„AI software company”** (SOP → role → artefakty); raczej **greenfield** niż SWE-bench issue fix.

## Streszczenie (PL)

MetaGPT (ICLR 2024) koduje **Standardized Operating Procedures** w prompty: Product Manager → Architect → Project Manager → Engineer → QaEngineer. Filozofia: `Code = SOP(Team)`. Wejście: jednozdaniowy requirement; wyjście: PRD, design, tasks, kod, testy. Lepszy od naiwnego chat-MAS przy złożonych projektach; HumanEval/MBPP SoTA w paperze. Słabiej mapuje się na „napraw issue w legacy monorepo” niż SWE-agent/OpenHands.

## Pipeline (kształt)

1. Requirement (NL).  
2. PM → PRD / user stories.  
3. Architect → API, struktury, diagramy.  
4. ProjectManager → task breakdown, deps.  
5. Engineer → implementacja (+ opcjonalny review).  
6. QaEngineer → unit testy, pętla debug aż pass / max iter.  
7. Artefakty w repo projektu (Git-backed ProjectRepo).

## Narzędzia

- Role agents, shared message pool / documents.  
- Code generation & execution w workspace.  
- Rozszerzenia research (SPO, AOT — 2025).

## Testy

- **QaEngineer** pisze i odpala testy, iteruje przy failach (limit iteracji).  
- To nie jest harness SWE-bench; fokus na generowanym projekcie.

## Multi-agent

- **Tak — core feature.** Stałe role + SOP assembly line.  
- Komunikacja przez ustrukturyzowane dokumenty, nie tylko free chat.

## Limity

- Cascading errors mimo SOP.  
- Koszt wielu agentów / tokenów.  
- Słabe dopasowanie do dużych istniejących codebase’ów (issue→PR).  
- Wymaga dojrzałego orchestratora i limitów.

## Repozytoria i paper’y

| Zasób | URL |
|-------|-----|
| GitHub | https://github.com/FoundationAgents/MetaGPT |
| arXiv / HTML | https://arxiv.org/abs/2308.00352 · https://arxiv.org/html/2308.00352v7 |
| OpenReview ICLR 2024 | https://openreview.net/forum?id=VtmBAGCN7o |
