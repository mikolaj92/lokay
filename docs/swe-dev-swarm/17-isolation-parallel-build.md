# Isolation for a parallel build

Child of #1551. Analysis only. No runtime change.

## What exists

src/lokay/git_worktree.py worktree_dir puts one branch in one directory. The directory is the project root plus the branch name, with slashes replaced. Two branches do not share a working tree.

worktrees_layout is legacy or clone-siblings. clone-siblings roots the directory beside the clone, through project_worktree_root. The clone itself is not used as a second package worktree. The code refuses to treat the clone path as that branch directory.

The factory still starts one of those directories per repo. The occupancy rule is one open AI PR. A second package has no branch and no directory of its own.

The singleton lokay.lock is the process lock. It is not a per-package lock. Two writers inside one worktree would share the index, the approach file, and the test process.

## Gap

SWE-Dev Build runs packages at the same time. Each package needs a branch, a directory, and one writer. Sharing a package directory, or writing two packages into one worktree, races the git index.

Lokay can isolate branches. It does not create a branch per package, and it does not stop two agents from editing one directory, because the scheduler never starts the second agent.

## What not to pretend

clone-siblings is a layout for ticket branches. It is not package isolation. Separate directories still need a merge step, and that step does not exist.

## Smallest later change

When a package list exists, give each package its own branch and its own worktree_dir. One writer per directory. Integrate by merging those branches into the ticket branch. Do not share .lokay/approach.md across those directories.
