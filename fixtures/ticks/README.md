# Tick segments
A segment resumes recorded effects at a node boundary, not a complete tick invocation.
Source: read-only `~/.lokay/ticks/2026-10-18.jsonl`; no Temida data.
Plan/Build: `anonimizator3000#74`, tick `f09832d2-6b0f-429d-9fee-e80d395206a5` (00:45–00:50Z).
Check: `datasource-kit#96`, tick `bf5ee2c2-db77-4552-9f82-d3e92b9c2b7f`, seq 150–221 (02:18Z), verdict `fix`.
Check starts after dependency setup and ends at the verdict, before Fix or Merge.
Setup was not recorded as a call; its exact result comes from the seq 163 local-test log.
Plan comes from the read-only run directory; diff, source text and file names come from recorded outputs.
Empty files seed tracked paths; lock input uses recorded added lines; Git markers seed filesystem shape only.
Replay checks every call and transition, including the local test (316 passed) and `uv lock --check`.
Unrecorded effects, exceptions and mismatches fail closed; subprocesses and sockets stay blocked.
Run `uv run lokay replay fixtures/ticks/`; `scripts/check.sh` already runs it offline.
