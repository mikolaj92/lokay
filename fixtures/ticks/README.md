# Tick replay checks
A segment resumes `act()` from a recorded node boundary, not a complete tick invocation.
Source: read-only `~/.lokay/ticks/2026-10-18.jsonl`, tick `f09832d2-6b0f-429d-9fee-e80d395206a5`, `mikolaj92/anonimizator3000#74` (00:45–00:50Z).
Plan resumes after seq 121: entry precondition seq 72–79, then seq 122–148; accepted-plan comparison, synthesis, Build merge conflict and cleanup.
Build resumes after seq 131: entry precondition seq 122–129, then seq 132–148; merge conflict, failure transition and cleanup.
The entry preconditions are recorded worktree verification calls; every segment preserves their original order.
Only redacted recordings and referenced blobs are included; plans come from the recorded comparison input, and Git markers only seed filesystem shape.
Replay runs offline in a temporary sandbox, checks calls and transitions in order, and fails closed on unexpected effects.
Check is absent because successful paths require missing worktree contents and check artifacts; nested pi guard calls cannot replay as a flat stream.
Local test commands and `uv lock --check` now opt into the existing recorded call path, including redacted argv, stdin, return code, stdout/stderr and exception attempts in effect blobs.
Existing recordings lack these local test effects; a Check fixture must follow deployment and a new recording.
For that fixture, use `files` in the segment manifest to seed required worktree files and `plan.md` from read-only run artifacts or recorded call outputs (`ls-files` and diff); preserve the recorded paths and call order.
Do not fabricate missing effects or use Temida data. Keep the redacted fixture under 2 MB.
Fix needs source snapshots and pi filesystem changes; Merge also needs an unrecorded temporary checkout and its checks.
