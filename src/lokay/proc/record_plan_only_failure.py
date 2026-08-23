"""Record one terminated plan-only issue in the stuck ledger."""

from pathlib import Path
from lokay.stuck import load_stuck, record_failure, save_stuck


def record(stamped: dict, *, stuck_path: str) -> dict:
    stuck = load_stuck(Path(stuck_path))
    row = record_failure(
        stuck,
        repo=stamped["repo"],
        number=int(stamped["issue"]),
        error="plan_only",
        max_failures=1,
    )
    row["reason"] = "plan_only"
    save_stuck(Path(stuck_path), stuck)
    return {**stamped, "route": "park", "stuck": row}
