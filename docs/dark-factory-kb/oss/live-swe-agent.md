# Live-SWE-agent

**Nazwa EN:** Live-SWE-agent (OpenAutoCoder)  
**Rola w dark factory:** **self-evolving** scaffold na bazie mini-SWE-agent — agent rozszerza własne zdolności w runtime podczas rozwiązywania issue.

## Streszczenie (PL)

Insight: software agent **sam jest oprogramowaniem**; LLM może w locie dopisywać narzędzia / zmieniać zachowanie scaffoldu. Live-SWE-agent (2025) buduje na **mini-swe-agent** z minimalnymi modyfikacjami i osiąga bardzo wysokie wyniki OSS: raportowane m.in. **~79.2%** SWE-bench Verified (Claude Opus 4.5), **~77.4%** (Gemini 3 Pro), **~45.8%** SWE-Bench Pro. Cel: uczciwe porównanie modeli na lekkim, otwartym harnessie + demonstracja self-evolution.

## Pipeline (kształt)

1. Issue jak w mini-SWE-agent.  
2. Pętla bash/agent.  
3. **Live evolution:** w trakcie trajektorii agent może rozszerzyć/zmodyfikować własne capabilities.  
4. Verify / iterate.  
5. Patch output + artefakty trajektorii (release bundles).

## Narzędzia

- Dziedziczy minimalizm mini-SWE-agent (shell-centric).  
- Dodatkowo mechanizmy self-modification scaffoldu (patrz paper/repo).

## Testy

- Jak mini-SWE / SWE-bench protocol.  
- Publiczne trajektorie i patche w release v1.0.0.

## Multi-agent

- Single evolving agent (nie team ról).

## Limity

- Self-modification = ryzyko niestabilności / trudniejszy audit.  
- Wyniki silnie sprzężone z frontier LLM.  
- Nadal research harness, nie pełny product PR factory.

## Repozytoria i paper’y

| Zasób | URL |
|-------|-----|
| GitHub | https://github.com/OpenAutoCoder/live-swe-agent |
| Baza: mini-swe-agent | https://github.com/SWE-agent/mini-swe-agent |
| Paper (cytowanie z README) | Xia et al., *Live-SWE-agent: Can Software Engineering Agents Self-Evolve on the Fly?*, arXiv 2025 |
