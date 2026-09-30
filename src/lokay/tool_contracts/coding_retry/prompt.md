Your previous coding response JSON was invalid. Return ONLY one closed JSON object {verdict: implemented|needs_evidence, evidence_kind, summary, tests_run, residual_risk}. Validator feedback: <<feedback>>
For implemented, retain ALL five fields and set evidence_kind to JSON null (not a string, not omitted). It requests missing evidence; it does not describe evidence already used.
{"verdict":"implemented","evidence_kind":null,"summary":"Describe the actual implementation diff","tests_run":["Actual test command and result"],"residual_risk":"Describe remaining risk"}
Only needs_evidence uses a non-null evidence_kind from issue_snapshot, repo_structure, test_contract, localized_diff.
Invalid response: <<response>>
