# Poolside — Model Factory (not an SDLC mill)

**Archetype:** Adjacent — foundation-model industrialisation for *agentic coding models*  
**Do not confuse** “Model Factory” (train models) with “software factory” (ship product PRs).

## URLs
- https://www.poolside.ai/
- https://www.poolside.ai/research
- https://poolside.ai/blog/introducing-the-model-factory
- https://www.poolside.ai/blog/titan-the-model-factory-s-furnace — Titan training stack
- https://poolside.ai/blog/post-training-in-the-model-factory — SFT/RL post-training
- Laguna tech report PDF: https://poolside.ai/assets/laguna/laguna-m1-xs2-technical-report.pdf
- Laguna XS.2 weights (Apache 2.0): https://huggingface.co/collections/poolside/laguna-xs2

## Mechanism notes
- **Model Factory:** Internal platform turning model development into an industrial process — versioned data, training, eval, inference; automated eval during training; RL from **code execution**; synthetic data; data mixing; orchestrated across large GPU clusters (reports mention ~10K GPUs).
- **Code execution env:** ~1M GitHub repos built into OCI containers for RL/eval; agent-based container building (“agent improving the Factory that built it”).
- **Components named in blogs:** Titan (distributed training / SFT / RL), Atlas (inference), Blender (data blend/stream), Saucer (revision serving), Dagster orchestration, Podium dataset viewer, GPU↔GPU weight transfer.
- **Laguna M.1 / XS.2:** MoE models for long-horizon agentic coding (M.1 ~225.8B total / 23.4B active; XS.2 ~33.4B / 3B active). Competitive on SWE-bench family / Terminal-Bench class evals per tech report.

## Dark-factory distance
**Not a dark software factory product.** Relevant as **upstream model supplier** for mills that want coding-specialist weights / self-host. Org buying Poolside is buying model + training ops DNA, not ticket→PR orchestration.

## Polish
Poolside „Model Factory” to fabryka *modeli* agentycznego kodowania (Laguna, RL na egzekucji kodu), nie młyn ticket→PR. Ważny sąsiad ekosystemu dark factory, nie sam produkt SDLC.
