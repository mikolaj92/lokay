from lokay.proc.select_implementation_candidate import select
from lokay.passkit import io as pass_io


def test_selects_only_one_candidate(tmp_path):
    pass_io.write_json(pass_io.begin_path(tmp_path), {"live": True, "stuck": {}})
    pass_io.write_json(
        pass_io.working_path(tmp_path),
        {"ready_by_repo": {"a/b": [{"number": 2}, {"number": 1}]}},
    )
    pass_io.write_json(
        pass_io.implement_path(tmp_path), {"issue_budget": 4, "clean_repos": ["a/b"]}
    )
    out = select(pass_dir=str(tmp_path))
    assert out["route"] == "candidate" and out["issue"] == 1


def test_no_live_budget_has_terminal_route(tmp_path):
    pass_io.write_json(pass_io.begin_path(tmp_path), {"live": False})
    pass_io.write_json(pass_io.working_path(tmp_path), {})
    pass_io.write_json(pass_io.implement_path(tmp_path), {"issue_budget": 4})
    assert select(pass_dir=str(tmp_path))["route"] == "none"
