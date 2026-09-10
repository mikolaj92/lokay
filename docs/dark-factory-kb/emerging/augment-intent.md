# Augment Intent

**Archetype:** Spec-driven multi-agent orchestration workspace (B→C)  
**Vendor line:** “What comes after the IDE.”

## URLs
- https://www.augmentcode.com/blog/intent-a-workspace-for-agent-orchestration
- Intent app surface referenced as intentapp.dev in secondary comparisons
- Augment Context Engine MCP commonly paired

## Mechanism notes
- **Coordinator agent** drafts a living **spec/plan** using Augment Context Engine → **human approval gate** → **implementor agents** in parallel isolated worktrees → **verifier** checks against spec → diffs → optional **PR Shepherd** toward merge-ready.
- **BYOA:** Native Auggie recommended; also Claude Code, Codex, OpenCode.
- **Contrast to Devin:** Explicit orchestration + mandatory plan approval vs “delegate and wait.” Less unattended dark factory, more controlled swarm.
- **Limits (secondary):** Public beta / Apple Silicon notes in comparisons; scheduling/API for agents-launching-agents thinner than some CLI orchestrators (e.g. Superset claims).

## Dark-factory distance
**Human-gated C.** Excellent pattern for serious eng orgs that refuse blind autonomy: spec approval is the limbo they *want*. Not zero-human-limbo.

## Polish
Intent = workspace orkiestracji: koordynator pisze spec → człowiek zatwierdza → paralelni implementorzy + weryfikator. Filozofia „po IDE”, ale z twardą bramką planu — anty-Devin w kwestii kontroli.
