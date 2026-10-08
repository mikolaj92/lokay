# Integrate and test layers

Child of #1551. Analysis only. No runtime change.

## What exists

There is no integrate atom. Nothing stitches package branches, because the slot has one worktree and one branch.

src/lokay/proc/test_local.py declared_test_argv resolves one command. An explicit tool.lokay.test wins. Otherwise it picks one native command. Pixi full-smoke, test, or core-smoke. Swift test when Package.swift exists. uv pytest when the project declares pytest.

When more than one of those commands exists, the function joins them with a shell && . That is still one argv. The first failure stops the rest. The receipt is one exit status, not a layer name.

Changed pytest files can narrow that argv. The narrow run is still the same layer, not a new one.

## Gap

SWE-Dev Integrate stitches finished packages and then runs every test layer. Lokay never has finished packages to stitch. Its test stack is the declared command list, run once, in order, in the same worktree.

A second layer would need its own name and its own receipt. Joining commands with && does not record which layer failed.

## What not to pretend

Pixi, Swift, and pytest in one shell line are not the SWE-Dev layers. They are host-native fallbacks for whatever repo the ticket touched. There is no package stitch hiding inside test_local.

## Smallest later change

Name each declared command as a layer and store its exit status separately. Add an integrate step only after two package branches exist to merge. Do not add that step in this note.
