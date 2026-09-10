# Wave F — finds log (local CLI / daemon klepacz)

**Data:** 2026-09-10 (PT / Europe/Warsaw)  
**Filtr:** lokalne CLI/daemon w kształcie **klepacz** (spec/TASKS/label → implement → commit/PR), keywordy użytkownika.  
**Skip:** wszystkie istniejące slugi w `instances/` (m.in. `eugeneorlov-noxdev`, `ableinc-coding-agent-loop`, `robotsix-mill`, `finn-loop`, …).  
**Karty:** `instances/<slug>/README.md` (mermaid + Confidence + linki, PL)

## Keywords → trafienia

| Keyword | Karty |
|---------|-------|
| ralph wiggum loop | michaelshimeles-ralphy, mikeyobrien-ralph-orchestrator, th0rgal-open-ralph-wiggum |
| coding agent loop | ralphy, open-ralph, ralph-orchestrator |
| overnight agent | jhostalek-junior, a20185-overnightagent, jessekaff-trismegistus |
| TASKS.md agent | tasksmd-tasks-md, jessekaff-trismegistus, ralphy (`--prd tasks.md`) |
| worktree fleet | ralphy `--parallel`, junior, overnightagent, os-factory-har |
| issue implementer harness | okeyamy-forge, salehaiftikharr-agent-forge, os-factory-har |
| forge mill CLI | okeyamy-forge, forge-sdlc-forge, salehaiftikharr-agent-forge |

## Karty napisane (11 NEW)

| Slug | ★ | Klepacz? | Confidence | Uwagi |
|------|---|----------|------------|-------|
| [michaelshimeles-ralphy](michaelshimeles-ralphy/) | 2969 | tak — label/PRD→worktree→PR | 92 | Najmocniejszy local mill w fali |
| [mikeyobrien-ralph-orchestrator](mikeyobrien-ralph-orchestrator/) | 3132 | partial — loop+tasks+gates | 88 | Orkiestracja Ralph; PR osobno |
| [th0rgal-open-ralph-wiggum](th0rgal-open-ralph-wiggum/) | 1885 | partial — czysta pętla | 80 | Multi-agent `ralph` CLI |
| [jhostalek-junior](jhostalek-junior/) | 6 | tak — queue→worktree→merge | 82 | Overnight daemon + flota |
| [a20185-overnightagent](a20185-overnightagent/) | 1 | tak — plan→verify→commit | 78 | 4-gate verify + detach |
| [okeyamy-forge](okeyamy-forge/) | 5 | tak — label `forge`→branch | 86 | Textbook watch mill |
| [forge-sdlc-forge](forge-sdlc-forge/) | 20 | tak — Jira→PR (+plan) | 75 | Grubszy SDLC forge |
| [os-factory-har](os-factory-har/) | 88 | harness — flota+verify | 72 | Podklejenie pod klepacza |
| [tasksmd-tasks-md](tasksmd-tasks-md/) | 8 | kolejka — `/next-task`+fleet | 70 | Spec TASKS.md |
| [jessekaff-trismegistus](jessekaff-trismegistus/) | 0 | tak — tasks.md daemon | 62 | Bez worktree |
| [salehaiftikharr-agent-forge](salehaiftikharr-agent-forge/) | 0 | tak — ticket→gated PR | 74 | Minion prove-then-PR |

## Odrzucone / odłożone

| Kandydat | Powód |
|----------|-------|
| **eugeneorlov/noxdev** | Już karta `eugeneorlov-noxdev` |
| **ableinc coding-agent-loop** | Już `ableinc-coding-agent-loop` |
| **saman-ns/meeseeks-loop** | Fork ralphy ★0 — nie duplikować bez różnicy produktowej |
| **ghuntley/how-to-ralph-wiggum** | Metodologia/docs, nie CLI mill |
| **anthropics ralph-wiggum plugin** | Stop-hook w Claude Code — nie osobny local daemon; vendor plugin |
| **jooray/night-agent** | Overnight maintenance; **never pushes** — nie ticket→PR |
| **devflowinc/uzi**, **standardagents/dmux**, **raine/workmux** | Worktree multiplexers bez kolejki ticket/label |
| **majiayu000/harness** | Fleet control plane / governance — bliżej platformy niż klepacz; HAR wystarczy jako harness |
| **coreyepstein/ralph-methodology** | Docs only ★4 |

## Preferencje jakości (Wave F)

1. **michaelshimeles-ralphy**, **okeyamy-forge**, **jhostalek-junior** — najwyższy stosunek „realna lokalna mrówka / marketing”.  
2. **ralph-orchestrator** / **open-ralph** — kanon pętli; dokleić PR/label samemu.  
3. **forge-sdlc-forge** — gdy potrzeba Jira+CI repair, nie bash overnight.  
4. **tasks.md** + **trismegistus** — warstwa kolejki; łączyć z worktree mill.

## Metoda

WebSearch (keywordy) + `gh api repos/…` metadata + README fetch. Cross-check listy `instances/` przed zapisem slugów.
