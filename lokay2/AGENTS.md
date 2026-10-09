# lokay2

The graph is Plan, Build, Check, Fix, Merge. Merge is the only end.

A step ends as JSON on stdout. Decision steps print `next`. LLM and code steps print `result`. Fala reads only that field. A transport failure prints nothing and exits non-zero.

`pi -p` writes code. Decision steps return probabilities, not prose. Do not import `lokay` from `src/lokay`.

No unit tests of this package. A scenario script or a real run is the proof. Auto-merge is on for every repo. The only human approval is the nuke PR.
