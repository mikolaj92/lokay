# Implementer, tester, and package critic

Child of #1551. Analysis only. No runtime change.

## What exists

One coding executor writes the patch. docs/WORKING.md sequences the slot as plan_issue, then the configured executor, then commit, rebase, tests, push, and a PR.

src/lokay/proc/test_local.py is the test step. It reads the repository's declared test command and can target pytest files that changed. It is not an agent. It does not write a critique. It returns the command result.

A search of the tree finds no package critic. There is no per-package role split inside the one worktree.

## Gap

SWE-Dev Build gives each package three roles. An Implementer writes the package. A Tester writes and runs its tests. A package critic accepts or rejects that package before integrate.

Lokay has one writer and one test command. The test command does not say whether the tests cover the package. It only says whether the declared command passed. With no packages, there is nowhere to hang the third role.

## What not to pretend

test_local is not a Tester agent. The coding executor is not three roles sharing one prompt. A green test run is not a package critique.

## Smallest later change

After a package list exists, run the declared test command once per package and store its exit status next to that package. Add the critic only after that result has a place to land. Do not split the coding executor in this note.
