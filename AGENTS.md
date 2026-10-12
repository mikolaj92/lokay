# lokay

The graph is Plan, Build, Check, Fix, Merge. Merge is the only end.

`lokay start` runs the only graph, in Python (`src/lokay/start.py`). Decision steps return `next`. LLM and code steps return `result`. The runtime retries failed steps, checks revised plans again, and returns from Fix to Check.

`pi -p` writes code. Decision steps return probabilities, not prose. Do not import `lokay` from `src/lokay`.

No unit tests of this package. A scenario script or a real run is the proof. Auto-merge is on for every repo. The only human approval is the nuke PR.
