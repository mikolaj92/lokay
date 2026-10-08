"""Blueprint node dispatcher. Bodies stay stubs until later tickets.

Run: python -m lokay.nodes <effector_id> with a JSON request on stdin.
"""
import json
import sys

TICK = (
    "tick_lease", "observe_github", "observe_host", "doctor", "host_action",
    "settle", "failure", "admit", "stale", "plan", "admission", "pick", "launch",
)
BLUEPRINT = (
    "claim", "worktree", "context", "code", "commit", "test", "after_code",
    "fix", "commit2", "test2", "after_fix", "route", "publish_pr", "review",
    "lens_score", "disposition", "publish_verdict",
)
NODES = frozenset(TICK + BLUEPRINT)


def dispatch(effector_id, request):
    if effector_id not in NODES:
        return {'ok': False, 'terminal': 'contract_failed', 'reason': effector_id}
    return {'ok': True, 'terminal': 'stub', 'effector': effector_id, 'request': request}


def main(argv):
    effector_id = argv[1] if len(argv) > 1 else ''
    raw = sys.stdin.read() or '{}'
    request = json.loads(raw)
    result = dispatch(effector_id, request)
    json.dump(result, sys.stdout)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
