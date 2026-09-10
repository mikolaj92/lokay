# AutoCodeRover

**Nazwa EN:** AutoCodeRover (NUS APR / Abhik Roychoudhury et al.)  
**Rola w dark factory:** **SE-oriented** agent: AST/API search + opcjonalnie SBFL → patch na GitHub issues.

## Streszczenie (PL)

W przeciwieństwie do „AI-first” agentów z wolnym bash’em, AutoCodeRover traktuje projekt jako **strukturę programu** (AST: klasy/metody), nie worek plików. LLM woła **program-structure-aware code search APIs**, iteracyjnie zbiera kontekst, lokalizuje miejsce naprawy i generuje patch. Gdy są testy — **spectrum-based fault localization (SBFL)** ostrzy lokalizację. ISSTA 2024; publiczne wyniki m.in. ~19% SWE-bench-lite (wczesne), później wyższe warianty; koszt rzędu **~$0.43–0.7 / issue**. Następca funkcjonalny: **SpecRover**. Bliżej **stałego grafu** niż swobodnego tool-calling — zgodne z „deterministyczny pipeline + LLM w węzłach”.

## Pipeline (kształt)

1. Issue (bug / feature).
2. Iteracyjne **code search** po API strukturalnych (metoda w klasie, sygnatury…).
3. Opcjonalnie SBFL / reproduce z testów.
4. Generacja patcha.
5. Review/self-fix → regression.
6. Walidacja (testy dostępne agentowi / harness SWE-bench).

## Narzędzia

- Search APIs na AST (nie tylko ripgrep-string).
- LLM backend (multi-model).
- Integracja ze strukturą repo SWE-bench.

## Testy

- Jeśli suite dostępny → SBFL + regression.
- Acceptance SWE-bench nie używane przy generacji (reguła benchmarku).
- Orientacja na **program repair / improvement**.

## Multi-agent

- Głównie **jeden agent z tool-API**; SpecRover dokłada ReviewerAgent.

## Limity

- Słabszy na zadaniach wymagających szerokiego exploratory bash / web.
- Skupiony na Python/SWE-bench historycznie.
- Publiczna wersja vs wyniki „website” mogą się różnić.
- Greenfield / multi-service org poza scope paperów.

## Repozytoria i paper’y

| Zasób | URL |
|-------|-----|
| GitHub | https://github.com/nus-apr/auto-code-rover |
| Website | https://autocoderover.dev/ |
| arXiv | https://arxiv.org/abs/2404.05427 |
| ACM ISSTA 2024 | https://doi.org/10.1145/3650212.3680384 |
