# Agent role schema

Child of #1551. Analysis only. No runtime change.

## What exists

src/lokay/config.py stores one executor. agent_command defaults to pi. The comment says LOKAY_AGENT is only a log label. The binary is executor.command. An empty command is a config error.

Review is a second command. pr_review_plugin_command plus pr_review_plugin_args is required when structured review is on. pr_review_sandbox_command is the OS sandbox. pr_review_model and pr_review_models name lenses, not roles.

src/lokay/models.py has an Issue dataclass. It has no AgentSpec and no role enum. A search of the config finds no Architect, Critic, Implementer, Tester, Integrator, or Fixer field.

## Gap

The epic wants those roles mapped onto Fala atoms, plugins, and one AgentSpec-shaped JSON. Lokay has two command slots. The executor writes the patch. The review plugin reads the PR. Triage, tests, and merge are Python atoms, not agents.

A lens model string is not a role. Reusing the same executor.command under seven names would hide which prompt ran.

## What not to pretend

The log label is not a role schema. Two commands are not eight roles. Fala atoms that run Python are not agents.

## Smallest later change

Add one role record with name, command, args, and the Fala atom that may call it. Start with the two commands that exist. Leave Architect, Critic, Tester, Integrator, and Fixer absent until a ticket gives each a command.
