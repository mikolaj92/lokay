# Agentless

**Nazwa EN:** Agentless (OpenAutoCoder)  
**Rola w dark factory:** **pipeline bez autonomicznego tool-loop** — localization → repair → patch validation.

## Streszczenie (PL)

Agentless argumentuje, że pełna autonomia agentów (planowanie + narzędzia ad hoc) nie jest konieczna do rozwiązywania GitHub issues. Zamiast tego: **ustalone trzy fazy**. Historycznie jeden z najlepszych OSS wyników koszt/skuteczność na SWE-bench lite (~27% @ ~$0.34, potem ~40%+ lite / ~50% verified z Claude 3.5). Paper: *Demystifying LLM-based Software Engineering Agents* (arXiv 2407.01489). Pokazuje, że **prosty scaffold + dobry model** bije wiele „agentowych” systemów — argument za cienkim harnessem zamiast „agent z 40 toolami”.

## Pipeline (kształt)

1. **Localization:** hierarchicznie zawęża pliki / elementy (struktura repo).
2. **Repair:** generuje kandydatów patchy (często multi-sample).
3. **Patch validation:** selekcja / filtrowanie (np. przez testy reprodukujące / regression w kontrolowanym env).
4. Submit najlepszego patcha.

Brak swobodnego „agent wybiera kolejne narzędzie w ReAct”.

## Narzędzia

- Preprocessing struktury repo.
- LLM prompting w stałych etapach.
- Skrypty ewaluacji SWE-bench / Docker.

## Testy

- Faza walidacji używa uruchamiania testów do odsiania złych patchy.
- Zgodność z protokołem SWE-bench (acceptance ukryte przy generacji).

## Multi-agent

- **Nie** — świadomie *agentless*. Porównanie w paperze vs SWE-agent, Aider, Moatless, ACR, SpecRover.

## Limity

- Sztywny pipeline: gorzej przy zadaniach wymagających eksploracji / instalacji / web.
- Mniej elastyczny poza SWE-bench-like bugfix.
- Brak interaktywnego IDE UX.

## Repozytoria i paper’y

| Zasób | URL |
|-------|-----|
| GitHub | https://github.com/OpenAutoCoder/Agentless |
| arXiv PDF | https://arxiv.org/pdf/2407.01489 |
| arXiv abs | https://arxiv.org/abs/2407.01489 |
