# Moatless Tools (+ SWE-Search)

**Nazwa EN:** Moatless Tools, Moatless Tree Search / SWE-Search  
**Rola w dark factory:** **tool-first** agentic loop (locate → edit → verify); opcjonalnie **MCTS** przy inference-time scaling.

## Streszczenie (PL)

Hobby/research Albert Örwall: zamiast polegać na „rozumowaniu” agenta, buduje **dobre narzędzia** wkładające właściwy kontekst i parsujące odpowiedź. Locate (AST + semantic index + FS), Edit (kontrolowane diffy), Verify (Docker + zwięzły feedback z testów). **SWE-Search** (arXiv 2410.20285) dokłada Monte Carlo Tree Search / iterative refinement. Raportowane wyniki m.in. Claude 4 Sonnet ~**70.8%** solve rate @ ~$0.63/instance (README Moatless; weryfikuj aktualne eval pages).

## Pipeline (kształt)

1. Indeksowanie / retrieval kodu.  
2. **AgenticLoop** jako FSM stanów narzędzi.  
3. Edit w kontrolowanym formacie.  
4. Verify w kontenerze → feedback do LLM.  
5. (SWE-Search) drzewo poszukiwań, refinement ścieżek.

## Narzędzia

- Code index + Voyage embeddings (dla SWE-bench precomputed).  
- Semantic / AST search.  
- Diff editing.  
- Docker verification.  
- Flow’y: function-calling vs ReACT (pod OSS modele).

## Testy

- Centralne: **Verify** parsuje wyniki testów do krótkiego feedbacku dla modelu.  
- Eval scripts pod SWE-bench splits.

## Multi-agent

- Raczej **single agent + tools**; tree search = wiele ścieżek, nie „role company”.

## Limity

- Skupienie na SWE-bench / Python.  
- Wymaga kluczy embedding (Voyage) dla gotowych indeksów.  
- Nie jest pełną platformą produktową (PR/UI org).

## Repozytoria i paper’y

| Zasób | URL |
|-------|-----|
| Moatless Tools | https://github.com/aorwall/moatless-tools |
| SWE-Search / tree-search | https://github.com/aorwall/moatless-tree-search |
| PyPI | https://pypi.org/project/moatless/ |
| SWE-Search arXiv | https://arxiv.org/abs/2410.20285 |
| Eksperymenty | https://experiments.moatless.ai/ |
