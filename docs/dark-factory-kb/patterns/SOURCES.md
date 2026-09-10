# Bibliografia: autonomiczne fabryki oprogramowania / dark factory / AI SWE agents (2024–2026)

Źródła użyte przy syntezie `PATTERNS.md` i `ANTI_PATTERNS.md`. Grupy tematyczne; w każdej — URL + krótka adnotacja. Stan zbioru: **2026-09-10**.

**Liczba wpisów:** 48

---

## 1. Metafora dark factory / drabina autonomii

1. https://www.danshapiro.com/blog/2026/01/the-five-levels-from-spicy-autocomplete-to-the-software-factory/ — Dan Shapiro, *The Five Levels: from Spicy Autocomplete to the Dark Factory* (2026-01-23); kanoniczna drabina L0–L5 i metafora FANUC.  
2. https://danshapiro.spicytakes.org/post/2026-01-23-the-five-levels-from-spicy-autocomplete-to-the-software-factory — mirror / streszczenie Five Levels.  
3. https://aipatternbook.com/dark-factory — *Dark Factory* w Encyclopedia of Agentic Coding Patterns; definicja, siły, StrongDM manifesto.  
4. https://env.dev/guides/ai-dark-factory — primer AI Dark Factory; holdout evaluator, case studies StrongDM/OpenAI/Anthropic/Spotify/Stripe.  
5. https://env.dev/ai/agentic-coding-levels — Agentic Coding Levels (Shapiro) jako leksykon.  
6. https://www.mindstudio.ai/blog/what-is-dark-factory-autonomous-ai-codebase — wprowadzenie „dark factory codebase”.  
7. https://itmethods.com/insights/governed-dark-factory — *The Software Factory Is Going Dark. The Audit Trail Cannot.* — governance / audit trail.  
8. https://developertoolkit.ai/en/ladder/state-of-agentic-engineering-2026/ — *State of Agentic Engineering, August 2026*; tabela L0–L5.  
9. https://www.emergentmind.com/papers/2604.09388 — AI Codebase Maturity Model (ACMM); krytyka utożsamiania autonomii z dojrzałością.

---

## 2. Software factory (produkty, whitepapery, case studies)

10. https://factory.ai/news/software-factory — Factory.ai, *Factory 2.0: From coding agents to software factories*.  
11. https://factory.ai/software-factory-whitepaper — *Software Factory* white paper: maturity model, filary, DMASI.  
12. https://www.uber.com/us/en/blog/efficient-software-factory/ — Uber, *Running a Software Factory Efficiently at Uber Scale* (AI Engineer 2026); warstwy, koszt, managed agents.  
13. https://github.com/miniforge-ai/miniforge — Miniforge: autonomous software factory (nested loops, policy gates, PR monitor).  
14. https://www.augmentcode.com/guides/what-is-a-software-factory — Augment: definicja agentic software factory.  
15. https://www.truefoundry.com/blog/software-factory-agentic-enterprise-guide — TrueFoundry: historia, architektura, enterprise controls.  
16. https://re-cinq.com/blog/building-agent-factories — *Building Software Factories: The Blueprint for AI-Native Delivery* (2026-03).  
17. https://www.agentnative.dev/agentic-software-factories — Agent Native: książka / playbook production line.  
18. https://ona.com/stories/software-factory-what-we-learned — Ona: fabryka w 10 dni (375 PR, 87% bez człowieka).  
19. https://agentictrustframework.ai/specification/maturity-model — Agent Maturity Model (Intern→Principal) + AWS scoping.

---

## 3. Agenci SWE, ACI, pipeline’y badawcze

20. https://papers.neurips.cc/paper_files/paper/2024/file/5a7c947568c1b1328ccc5230172e1e7c-Paper-Conference.pdf — Yang et al., *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering* (NeurIPS 2024).  
21. https://github.com/SWE-agent/SWE-agent — implementacja SWE-agent.  
22. https://arxiv.org/abs/2404.05427 — AutoCodeRover: Autonomous Program Improvement (ISSTA 2024).  
23. https://zhiyufan.github.io/files/ISSTA2024a.pdf — PDF AutoCodeRover.  
24. https://arxiv.org/html/2511.00872 — empiryczne porównanie frameworków agentowych na zadaniach code-centric.  
25. https://journal.kernelxos.com/jsec/article/download/23/43 — przegląd architektury autonomous SWE agents (perception, planning, ACI, memory, verify).  
26. https://devin.ai/blog/introducing-pr-stacks — Cognition Devin: stacked PRs, rebase, CI monitor.  
27. https://www.deployhq.com/guides/devin — przewodnik Devin w pipeline issue→PR→deploy.  
28. https://www.openhands.dev/blog/devin-ai-alternatives — OpenHands vs managed agents; control plane.  
29. https://wetheflywheel.com/en/comparisons/openhands-vs-aider/ — OpenHands vs Aider (2026); sandbox agent vs pair-programmer.  
30. https://github.com/arenstar/optio — Optio: task→PR→CI feedback→auto-merge; pod-per-repo + worktrees.

---

## 4. Ewaluacja (SWE-bench i pokrewne)

31. https://github.com/SWE-bench/SWE-bench — SWE-bench repo + harness Docker.  
32. https://www.swebench.com/SWE-bench/guides/evaluation/ — oficjalny przewodnik ewaluacji.  
33. https://github.com/swe-bench/swe-bench/blob/main/docs/guides/evaluation.md — evaluation.md (cache run_id, artefakty).  
34. https://github.com/TuringEnterprises/SWE-Bench-plus-plus — wariant harness / dokumentacja run_evaluation.  
35. https://github.com/nexus-substrate/nexus-eval-swebench — adapter ewaluacyjny SWE-bench dla nexus-agents.

---

## 5. Orkiestracja (LangGraph, Temporal, grafy)

36. https://temporal.io/blog/temporal-langgraph-plugin-durable-execution — Temporal × LangGraph: durable execution, interrupts, continue-as-new.  
37. https://docs.temporal.io/develop/python/integrations/langgraph — dokumentacja integracji Temporal–LangGraph.  
38. https://github.com/temporalio/sdk-python/pull/1448 — PR: LangGraph plugin (activities, interrupt, cache).  
39. https://python.temporal.io/temporalio.contrib.langgraph.LangGraphPlugin.html — API LangGraphPlugin.

---

## 6. Locki, occupancy, merge-train, multi-repo, fail-closed

40. https://github.com/luohoa97/agent-locks — filesystem locks w git common-dir dla równoległych worktree.  
41. https://github.com/openagentlock/OpenAgentLock/blob/main/docs/guide/policies.md — deterministyczne YAML gates, deny-overrides, brak `ask`.  
42. https://github.com/Gentoflakes/warden — worktree isolation + independent fail-closed audit + merge digest.  
43. https://github.com/yongjip/mergetrain — merge-train, runner lock, multi-repo hub, atomic push.  
44. https://cdn.jsdelivr.net/npm/@lbk-open/super-spec@0.1.1/docs/worktree-and-multi-repo.md — multi-repo: osobny proces per root, go/no-go, zakaz mid-run HITL.

---

## 7. Uzupełniające (przemysł, analogie, kontekst)

45. https://env.dev/guides/ai-dark-factory — (też §1) FANUC Yamanashi jako analogia lights-out; ekonomia tokenów StrongDM.  
46. https://www.agentnative.dev/agentic-software-factories — SWE-bench Verified saturation / koszt maszynowania jako tło fabryk.  
47. https://factory.ai/news/software-factory — spektrum autonomii: skills / automations / missions.  
48. https://www.uber.com/us/en/blog/efficient-software-factory/ — self-healing CI, managed agent roadmap, context-graph.

---

## Indeks szybkiego wyszukiwania

| Temat | ID źródeł |
|-------|-----------|
| Dark factory / Shapiro L5 | 1–9 |
| Factory.ai / Uber / Miniforge | 10–13, 47–48 |
| Case studies (Ona, StrongDM via env.dev) | 4, 18 |
| SWE-agent / AutoCodeRover / Devin / OpenHands | 20–30 |
| SWE-bench harness | 31–35 |
| Temporal / LangGraph | 36–39 |
| Locks / merge-train / fail-closed | 40–44 |
| Maturity / trust / audit | 7, 11, 19, 9 |

---

## Uwagi metodologiczne

- Termin **„dark factory”** w softwarze: Shapiro (2026) + społeczność; nie mylić z „harness engineering” (Kropp) ani z równaniem Agent = Model + Harness (Böckeler) — to **przesłanki**, nie synonimy.  
- Wiele liczb case-study (LOC/dzień, PR/tydzień) pochodzi z komunikacji firmowej / relacji wtórnych — traktować jako **orientacyjne**, nie niezależny benchmark.  
- Wzorce w `PATTERNS.md` są **abstrakcyjne**; linki tu dokumentują pochodzenie idei, nie endorsment konkretnego vendora.
