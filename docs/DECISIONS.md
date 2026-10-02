# Typed semantic decisions

Optional `decisions.endpoints` and `decisions.routes` select an explicit provider
for existing closed semantic slots. Without a route, the existing agent remains.
With a route, **no generative fallback or hidden retry** is allowed.

| Route | Production endpoint | Responsibility |
|---|---|---|
| `intake_ambiguity` | GB10 GLM `/v1/decisions` | pass / split / insufficient scope; explicit `issue_scope_decision` atom before triage |
| `issue_triage` | GB10 GLM `/v1/decisions` | ready / split / live host-ops routing / named evidence request / skip |
| `queue_conflict` | GB10 GLM `/v1/decisions` | independent / contradictory / superseded / tracker with children; configured executor admission uses the actual candidate and fresh peer/PR evidence |
| `relocalization` | GB10 GLM `/v1/decisions` | all off-goal changes necessary / unrelated / insufficient evidence; fail closed on uncertainty |

One invocation sends **one question in one HTTP POST**, not one request per path.
Evidence enrichment is the existing separate authored node and can run once.
The live profile routes **all four decisions to GB10**, with exact served identity
`GLM-5.3-Flash-EXL3`; no Plumb route or fallback. The factory issue-triage graph
invokes `issue_scope_decision` after hard facts and before triage; its result is
advisory scope evidence, not a second source of authority for ready/host-ops routing.
Evidence enrichment reuses this scope result instead of calling the scope model again.

The live sieve selects **undecided inbox issues**, not the executor's ready-only
queue. Its `issue-sieve-tail.json` beside `state_path` rotates remaining inbox
work across passes; `issue-sieve.json` inside each pass retains the original
finite budget on resume. Neither is an executor authorization or a budget reset.
The executor remains ready-only. After physical PR-first admission, a configured
queue check uses the real candidate body and fresh source peer/PR evidence in one
model call; anything other than accepted `ready` skips that candidate and advances
the pass tail. A deterministic PR-first refusal also advances the pass tail before
any queue-model call, without spending launch budget or mutating the blocked issue.
It does not close GitHub issues or add tracker labels. The legacy
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
The live profile uses only the GB10 `decisions` endpoint. The optional `systemone`
protocol remains supported for other explicit configurations. Do not include
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

## Generative agents and full review

The live executor argv pins `--provider omniroute --model
gb10/GLM-5.3-Flash-EXL3 --thinking off`. Register that exact model in Pi's
`~/.pi/agent/models.json` on the host. Discovery, localization, planning, splitting,
coding and repair all use the shared configured harness; deterministic checks are
not model calls. Do not use the `pi` combo alias, which can select other providers.
On the audited host the `gb10` provider points at `192.168.1.60:8888/v1` and has no
domain fallback chain. The LAN router is used for chat because Node cannot reach
the GB10 LAN endpoint directly on this Mac; decisions use system curl directly.

Full open-code-review must separately pin `gb10/GLM-5.3-Flash-EXL3` in its trusted
provider JSON and `pr_review.model`, then regenerate `config_sha256` and the operator
manifest with `expected_review_manifest`. Do not disable manifest validation.
A model alias, catalog entry or smoke is not proof of production coding/review use.

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
approvals / 3 false rejections**. Consequently the typed relocalization route was
previously disabled. Under the all-GB10 policy it is now configured, with the same
threshold and fail-closed rule; this routing change does **not** erase the known
false-rejection risk or establish semantic quality. No generative fallback.
A historical five-case Plumb queue panel accepted both independent cases; duplicate/conflict/
tracker cases all abstained below 0.85 and therefore skip. This is a tiny operational
panel, not calibration. No 4-bit/BF16 parity claim.

The all-GB10 migration panel (2026-10-02) is also diagnostic, not calibration:
- Scope: two coherent tasks passed; independent products and vague intent abstained.
- Queue: two independent tasks and a tracker classified as expected; a contradiction
  abstained; an identical duplicate was incorrectly admitted as independent at
  confidence 0.9699376838487097. This is a known false admission, not queue-quality PASS.
- Relocalization: again **0 false approvals / 3 false rejections** across six cases.

Live passage, production delivery and corpus validation must be reported separately
from these panels and hermetic contract tests.
