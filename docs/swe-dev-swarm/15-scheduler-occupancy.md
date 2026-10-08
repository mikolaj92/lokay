# Scheduler occupancy

Child of #1551. Analysis only. No runtime change.

## What exists

docs/WORKING.md gives the executor one open AI PR per repository. The pass budget defaults to 1. A second attempt in that repo does not start. Ready tickets behind that PR are waiting, frozen by per-repo occupancy.

A detached worker is occupancy, not delivery. The receipt outcome is a new PR, a merge, or none. Occupied, leftover skip, and an in-flight issue_to_pr also keep self-repair from starting.

src/lokay/proc/prepare_occupancy_refresh.py prepares the occupancy inputs for the authored slots. Too many inputs is an error. It does not create a second slot inside one repo.

Queue conflict runs before coding and can demote a contradictory issue. That is a semantic skip, not a scheduler for parallel stages.

## Gap

SWE-Dev fans Design, Build, and Review out inside one repo. Several packages would be several workers. Lokay treats a second worker in that repo as occupancy and waits.

Review of an open PR and coding of the next issue already share the repo lock. Adding Design and package builds on top would queue behind the same one-PR rule, or violate it.

## What not to pretend

K greater than 1 does not remove the per-repo lock. The docs limit that breadth to already-isolated clean repos. It is not a fan-out inside one catalog row.

## Smallest later change

Name the occupancy key. Today it is the repo. A later ticket can add a package id under that repo, still with one writer per id. Do not raise K in this note.
