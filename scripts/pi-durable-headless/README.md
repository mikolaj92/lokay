Build, Fix and plan writing use pi-durable 1.1.0 through its supported API.
Install with `npm ci --prefix scripts/pi-durable-headless`.
`LOKAY2_PI_BACKEND=classic` explicitly selects the previous backend; errors never trigger fallback.
Custom providers require `LOKAY2_PI_BASE_URL` and optionally `LOKAY2_PI_API_KEY`.
SQLite databases live in `$HOME/.local/state/lokay/pi-durable`, already writable under the existing sandbox.
Session identity includes repository, issue, node and plan history length; prompt hashes deduplicate submissions.
Local crash probe: SIGKILL before answer, reopen: conversation 1 and submission 8 unchanged, answer completed.
This probe used a local HTTP fixture, not a production model. Live Build/tick resumption and a durable-backed Lokay merge remain unverified.
