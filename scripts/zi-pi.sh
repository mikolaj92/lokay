set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec uv run --project "$ROOT" python -m lokay.effects.zi_pi "$@"
