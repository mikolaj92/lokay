# Graph tests

The authored source is `fala/lokay.fala-package.toml`. Its packaged copy must
remain byte-identical. Test count and copied node metadata are not delivery
coverage.

`issue_to_pr_delivery/test_graph.py` reads the authored graph and checks native
Fala match/miss behavior. `tests/test_issue_to_pr_fala.py` also exercises the real
parent bindings and a real Git diff with approved, denied and on-goal changes.
The generated per-node copies and their filename inventory audit were removed
for this path: they could stay green while the runtime lost issue and scope.

Other paths still contain generated graph snapshots. Their fixture-native
checks describe control-flow geometry, not successful product execution.
`tests/test_graph.py` checks authored output schemas used by branch conditions;
`tests/test_fala_package_lock.py` checks the checkout/package identity.
