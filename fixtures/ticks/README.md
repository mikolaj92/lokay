# Tick segments
One Check segment resumes `datasource-kit#96` after dependency setup and ends at the `fix` verdict.
Effects recorded 2026-10-18 02:18Z from read-only `~/.lokay/ticks/2026-10-18.jsonl`; no Temida data.
Expectations were re-recorded on current main; `weakened_tests` reports 6 removed test assertions.
Setup uses its recorded result; plan, diff, source text and file names come from recorded inputs.
Empty files seed tracked paths; lock input uses recorded added lines; Git markers seed filesystem shape only.
Replay checks consumed effects and transitions, including local tests (316 passed) and `uv lock --check`.
Unused recorded read-only Git calls may be skipped; other unmatched effects fail closed, with live processes and sockets blocked.
Re-record: `uv run lokay replay SOURCE/segment.jsonl --rerecord NEW_DIR` (one segment; only gh pr comment/edit `--body` may differ).
Run `uv run lokay replay fixtures/ticks/`; `scripts/check.sh` already runs it offline.
