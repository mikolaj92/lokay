# Typed semantic decisions

Optional `decisions.endpoints` and `decisions.routes` select an explicit provider
for existing closed semantic slots. Without a route, the existing agent remains.
With a route, **no generative fallback or hidden retry** is allowed.

| Route | Production endpoint | Responsibility |
|---|---|---|
| `intake_ambiguity` | local Plumb MLX `/v1/systemone` | pass / split / insufficient scope; explicit `issue_scope_decision` atom before GLM triage |
| `issue_triage` | GB10 GLM `/v1/decisions` | ready / split / live host-ops routing / named evidence request / skip |
| `queue_conflict` | local Plumb MLX `/v1/systemone` | independent / contradictory / superseded / tracker with children; configured executor admission uses the actual candidate and fresh peer/PR evidence |
| `relocalization` | agent retained; typed route available but NOT enabled | all off-goal changes necessary / unrelated / insufficient evidence |

One invocation sends **one question in one HTTP POST**, not one request per path.
Evidence enrichment is the existing separate authored node and can run once.
The factory issue-triage graph invokes Plumb in `issue_scope_decision` after hard
facts and before the GLM node; its result is advisory scope evidence, not a second
source of authority for ready/host-ops routing. This ensures the local model is used
by the real factory path, not only the standalone intake CLI. Evidence enrichment
reuses this scope result instead of calling Plumb again.

The live sieve selects **undecided inbox issues**, not the executor's ready-only
queue. Its `issue-sieve-tail.json` beside `state_path` rotates remaining inbox
work across passes; `issue-sieve.json` inside each pass retains the original
finite budget on resume. Neither is an executor authorization or a budget reset.
The executor remains ready-only. After physical PR-first admission, a configured
queue check uses the real candidate body and fresh source peer/PR evidence in one
model call; anything other than accepted `ready` skips that candidate and advances
the pass tail. It does not close GitHub issues or add tracker labels. The legacy
standalone queue graph retains its existing readiness-demotion effects.
Transport errors and malformed responses are terminal outcomes, not invitations
to retry. Relocalization approves the complete off-goal set or none, preserving
actual diff, HEAD/base identities and untracked contents before/after scoring.

SHA checks, file membership, GitHub state, repair budgets, test execution and merge
remain deterministic. File discovery, extraction of named paths, approach planning,
splitting into concrete child issues, coding and full PR review remain agents.
A model confidence score is **not proof that tests passed or authority to merge**.
Semantic guesses cannot close an issue; authoritative hard-fact close branches
remain unchanged. Queue `close` means demote readiness, not GitHub issue close.

## Configuration

See `config.live-autonomous.example.yaml`. Routes accept only the four names above.
Each endpoint requires explicit `url`, `protocol` (`systemone` or `decisions`),
exact response `model`, positive finite `timeout_seconds` (at most 180),
`min_confidence` (>0.5 through 1), and `max_input_chars` (at most 200000).
Use the exact served Plumb model path for its model identity. Do not include
credentials in URLs. These endpoints are trusted loopback/LAN services; the client
has no auth fallback and bypasses ambient proxy settings.

System curl is the only transport: macOS network permission is executable-specific
and uv Python on the deployment host cannot reach GB10 while `/usr/bin/curl` can.
Curl runs with no curlrc, redirects, retries, proxy or shell interpolation. TLS
verification is not disabled. Requests time out; response files are ephemeral.

Reject model/type/option identity mismatch, non-finite or unnormalized probabilities,
non-argmax choices and generated output. Under-threshold or tied choices abstain.
The initial threshold 0.85 is an operational abstention rule, **not measured
calibration**. Uncertain/unavailable intake is park (aggregate skip, no limbo stamp);
triage/queue skip; relocalization retains the hard off-goal failure.

## Evidence

Every HTTP attempt is appended durably to `decisions.jsonl` next to `state_path`.
It carries node, endpoint alias, served model, repo/issue/PR/HEAD/base identities
when supplied, evidence and complete request SHA-256, probabilities, confidence,
usage, duration and a named result. No fabricated PR/SHA for pre-coding issue-only
nodes. Full raw issue/diff text and credentials are not written to this journal.
If evidence cannot be recorded, the decision fails closed. Full numeric values
remain in this journal. On the Fala transport boundary, floating-point evidence
is carried as exact decimal strings: Python/native float spellings otherwise
produce different content-addressed result digests. No probabilities are rounded
and Fala digest validation remains enabled.

The known Plumb 4-bit initial smoke was 6/7; one misdelivery was misclassified
at confidence 0.403. That is below the configured acceptance threshold, but does
not establish model quality in Lokay. A six-case GLM scope panel rejected
all three necessary changes and admitted none of three unrelated changes: **0 false
approvals / 3 false rejections**. Consequently the typed relocalization route is
not enabled in production: the existing agent remains, not a per-call fallback.
A five-case Plumb queue panel accepted both independent cases; duplicate/conflict/
tracker cases all abstained below 0.85 and therefore skip. This is a tiny operational
panel, not calibration. Live passage and corpus validation must be reported
separately from hermetic contract tests. No 4-bit/BF16 parity claim.
