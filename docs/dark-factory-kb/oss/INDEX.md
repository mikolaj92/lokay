# Indeks: OSS / akademickie agenty „dark factory” (issue → patch → test → PR)

> Stan wiedzy: **2026-09-10**. Nazwy angielskie zachowane; streszczenia po polsku.
> Folder: `/workspace/dark-factory-kb/oss/`

## Czym jest „dark factory” w SE

Pipeline autonomicznego inżyniera oprogramowania: **wejście (issue/zadanie) → lokalizacja w repo → patch → uruchomienie testów → iteracja → commit/PR**. Komercyjne „dark factories” (Devin, Cursor Background Agents, Copilot Workspace, Factory, Cognition itd.) sprzedają to jako produkt z UI, billingiem, governance i SLA. Ten katalog opisuje **otwarte / akademickie** odpowiedniki i scaffoldy — oraz kilka OSS „godark” orkiestratorów.

## Mapa systemów (pliki)

### Research / SWE-bench scaffoldy

| Plik | System | Typ | Bliskość dark factory |
|------|--------|-----|------------------------|
| [swe-agent.md](./swe-agent.md) | **SWE-agent** / **mini-SWE-agent** | single-agent + ACI / bash | ★★★★★ |
| [openhands.md](./openhands.md) | **OpenHands** (ex-OpenDevin) | platforma + CodeAct | ★★★★★ |
| [autocoderover.md](./autocoderover.md) | **AutoCodeRover** | SE-oriented + AST search | ★★★★☆ |
| [specrover.md](./specrover.md) | **SpecRover** | ACR + spec + reviewer | ★★★★☆ |
| [agentless.md](./agentless.md) | **Agentless** | localize→repair→validate | ★★★★☆ |
| [moatless.md](./moatless.md) | **Moatless Tools** (+ SWE-Search) | tool-first + MCTS | ★★★★☆ |
| [live-swe-agent.md](./live-swe-agent.md) | **Live-SWE-agent** | self-evolving mini-SWE | ★★★★★ |

### Pair / IDE / CI

| Plik | System | Typ | Bliskość dark factory |
|------|--------|-----|------------------------|
| [aider.md](./aider.md) | **Aider** (+ pętle CI) | git-native pair + CI wrap | ★★★★☆ |
| [continue-dev.md](./continue-dev.md) | **Continue.dev** | IDE agent + CI review rules | ★★☆☆☆ |
| [refact.md](./refact.md) | **Refact** | local-first daemon + fleets | ★★★★☆ |
| [cline-opencode-goose.md](./cline-opencode-goose.md) | **Cline**, **OpenCode**, **Goose** | IDE/CLI agents | ★★★★☆ |

### Multi-agent „software company” / orkiestracja

| Plik | System | Typ | Bliskość dark factory |
|------|--------|-----|------------------------|
| [metagpt.md](./metagpt.md) | **MetaGPT** | SOP roles (greenfield) | ★★★☆☆ |
| [chatdev.md](./chatdev.md) | **ChatDev** | chat-chain waterfall | ★★★☆☆ |
| [metagpt-chatdev.md](./metagpt-chatdev.md) | MetaGPT/ChatDev skrót | porównanie | — |
| [magentic-one-autogen.md](./magentic-one-autogen.md) | **Magentic-One** / **AutoGen** | orchestrator + specialists | ★★★☆☆ |

### OSS orkiestratory „godark” (już w KB)

| Plik | System | Typ |
|------|--------|-----|
| [peter-stratton-dark-factory.md](./peter-stratton-dark-factory.md) | peter-stratton/dark-factory (godark) | orkiestrator |
| [gp-foundry.md](./gp-foundry.md) | gp-foundry | foundry |
| [0-sayed-dark-factory.md](./0-sayed-dark-factory.md) | 0-sayed/dark-factory | Codex+Archon+worktrees |

## OSS vs komercyjne dark factories — różnice

| Wymiar | OSS / akademia | Komercyjne dark factories |
|--------|----------------|---------------------------|
| **Cel** | Benchmarki (SWE-bench), paper, reproducibility, BYOK | Produkt: throughput ticketów, UX, retention |
| **Wejście** | Dataset issue / CLI prompt | Jira/Linear/GitHub Issues + Slack |
| **Sandbox** | Docker/podman lokalnie; user utrzymuje | Managed cloud VMs, egress, secrets vault |
| **PR / governance** | „Wygeneruj patch”; PR = skrypt usera | Natywne PR, branch policy, code owners, audit |
| **Multi-agent** | Role akademickie (PM/Arch/QA) lub orchestrator | Częściej jedna persona + tools + critic |
| **Testy** | Regression/reproducer w kontenerze; acceptance SWE-bench ukryte | CI org-a, flaky handling, coverage gates |
| **Koszt** | API key + compute; transparentne $/issue w paperach | Subskrypcja + usage; marża na modelu i infra |
| **Model** | Model-agnostic (litellm / OpenRouter / local) | Często zoptymalizowany pod własny/partner model |
| **Limity** | Słabe: long-term memory, multi-repo org, compliance | Słabe: lock-in, cena, black-box scaffolding |
| **Licencja** | MIT/Apache/BSD — fork i self-host | Proprietary SaaS; czasem open core |
| **Ewaluacja** | Publiczne leaderboardy (Verified ~70–79% z frontier LLM) | Marketing + prywatne evaly |

**Wniosek:** OSS najlepiej naśladuje **rdzeń pętli** (lokalizacja → edycja → test → patch). Komercja wygrywa **operacyjną obudową** (kolejki, tożsamość, secrets, review UX, multi-week memory, SLA). Najbliższe „prawdziwej” dark factory w OSS: **OpenHands**, **mini-SWE-agent / Live-SWE-agent**, **Refact** (local fleets), **Aider+CI**, orkiestratory godark. Najbliższe akademickiemu SE: **AutoCodeRover/SpecRover**, **Agentless**, **Moatless**.

## Szybkie URL-e kanoniczne

- SWE-bench: https://www.swebench.com/ · https://github.com/swe-bench/SWE-bench
- SWE-agent: https://swe-agent.com/ · https://github.com/SWE-agent/SWE-agent
- mini-SWE-agent: https://mini-swe-agent.com/ · https://github.com/SWE-agent/mini-swe-agent
- OpenHands: https://www.openhands.dev/ · https://github.com/OpenHands/OpenHands
- AutoCodeRover: https://github.com/nus-apr/auto-code-rover · https://autocoderover.dev/
- SpecRover: https://arxiv.org/abs/2408.02232
- Agentless: https://github.com/OpenAutoCoder/Agentless
- Moatless: https://github.com/aorwall/moatless-tools
- Live-SWE-agent: https://github.com/OpenAutoCoder/live-swe-agent
- Aider: https://aider.chat/ · https://github.com/Aider-AI/aider
- MetaGPT: https://github.com/FoundationAgents/MetaGPT
- ChatDev: https://github.com/OpenBMB/ChatDev
- Magentic-One: https://arxiv.org/abs/2411.04468 · https://microsoft.github.io/autogen/
- Continue: https://github.com/continuedev/continue
- Refact fork: https://github.com/JegernOUTT/refact
- Cline: https://github.com/cline/cline
- Goose: https://github.com/block/goose

## Konwencja

Każdy plik systemu: **Streszczenie (PL)**, **Pipeline**, **Narzędzia**, **Testy**, **Multi-agent**, **Limity**, **Repozytoria i paper’y (URL)**.
