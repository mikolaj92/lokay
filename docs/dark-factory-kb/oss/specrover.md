# SpecRover

**Nazwa EN:** SpecRover (AutoCodeRover-v2)  
**Rola w dark factory:** ACR + **inferencja intencji/specyfikacji** + agent recenzent patchy.

## Streszczenie (PL)

SpecRover (ICSE 2025) rozszerza AutoCodeRover o **iterative specification inference**: podczas przeszukiwania kodu generuje function-level summaries / intended behavior, reproduktory testów i przekazuje je **ReviewerAgent**, który weryfikuje patch + pewność (confidence/evidence dla developera). Na full SWE-bench (>50% poprawy względem ACR); koszt ~**$0.65 / issue** (SWE-bench lite, wg paperu). Pokazuje, że w erze LLM **specyfikacja nadal ma znaczenie** dla jakości naprawy.

## Pipeline (kształt)

1. GitHub issue.  
2. Strukturalny code search (jak ACR).  
3. Przy każdym odwiedzonym symbolu → **spec / function summary** pod kątem issue.  
4. Generacja **reproduction tests**.  
5. PatchAgent proponuje zmiany.  
6. **ReviewerAgent** krzyżuje: issue NL + specs + testy + patch → accept/reject + explanation.  

## Narzędzia

- Context retrieval APIs z ACR.  
- Function summary extraction.  
- Reviewer / selection agents.  
- Multi-LLM backend.

## Testy

- Generowane **reproducer tests** do selekcji patchy.  
- Regression w repo.  
- Reviewer może odrzucić zły test przy dobrym patchu (nie zakłada, że test = oracle).

## Multi-agent

- Tak: **Search / Patch / Reviewer** (role z papieru).  
- Explicit dual-check patch vs test.

## Limity

- Koszt dodatkowych wywołań LLM (spec + review).  
- Zależność od jakości inferencji intencji (halucynacje spec).  
- Nadal głównie benchmark SE, nie pełny product workflow PR.

## Repozytoria i paper’y

| Zasób | URL |
|-------|-----|
| arXiv | https://arxiv.org/abs/2408.02232 |
| PDF (autor) | https://haifengruan.com/assets/pdf/specrover_icse25.pdf |
| IEEE ICSE 2025 | https://doi.org/10.1109/ICSE55347.2025.00080 |
| Kod bazowy ACR | https://github.com/nus-apr/auto-code-rover |
| Zenodo artifacts (paper) | https://zenodo.org/doi/10.5281/zenodo.13161650 |
