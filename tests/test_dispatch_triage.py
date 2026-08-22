
from pathlib import Path

from lokay.passkit import io as pass_io
from lokay.proc import dispatch_triage


def _pass_dir(tmp_path: Path, *, stuck_path: Path) -> Path:
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "stuck_path": str(stuck_path),
            "live": True,
            "repos": [dispatch_triage.MINI_MILL_REPO],
        },
    )
    pass_io.write_json(
        pass_io.plan_path(pass_dir),
        {
            "triage_targets": [
                {"repo": dispatch_triage.MINI_MILL_REPO, "issue": 1},
                {"repo": dispatch_triage.MINI_MILL_REPO, "issue": 2},
            ]
        },
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {
            "actions": [],
            "progress": 0,
            "remaining_inbox": 2,
            "inbox_by_repo": {dispatch_triage.MINI_MILL_REPO: 2},
        },
    )
    return pass_dir




