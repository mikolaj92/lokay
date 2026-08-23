"""Native Fala proofs for bounded stale-worktree hygiene."""

from pathlib import Path
from test_issue_triage_fala import run_graph, base_effector


def test_keep_and_remove_are_direct_exclusive_edges(tmp_path):
    keep = tmp_path / "keep"
    remove = tmp_path / "remove"
    wrong = tmp_path / "wrong"
    body = base_effector(
        """if a=='collect_stale_worktree_candidates':v.update(candidate_1={'present':True},candidate_2={'present':True},candidate_3={'present':False},candidate_4={'present':False},deferred=[],receipt_safe=True)
if a=='classify_stale_worktree_1':v['route']='keep'
if a=='classify_stale_worktree_2':v['route']='remove'
if a in {'classify_stale_worktree_3','classify_stale_worktree_4'}:v['route']='absent'
if a=='keep_stale_worktree_1':Path(%r).write_text('ran')
if a=='remove_stale_worktree_2':Path(%r).write_text('ran')
if a in {'remove_stale_worktree_1','keep_stale_worktree_2','keep_stale_worktree_3','remove_stale_worktree_3','keep_stale_worktree_4','remove_stale_worktree_4'}:Path(%r).write_text(a)
if a=='summarize_stale_worktree_reap':v['result']={'kept_count':1,'reaped_count':1}"""
        % (str(keep), str(remove), str(wrong))
    )
    result = run_graph(tmp_path, body, "stale-routes", path_id="stale_worktree_reap")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        st["keep_stale_worktree_1"] == "succeeded"
        and st["remove_stale_worktree_1"] == "skipped"
    )
    assert (
        st["remove_stale_worktree_2"] == "succeeded"
        and st["keep_stale_worktree_2"] == "skipped"
    )
    assert keep.exists() and remove.exists() and not wrong.exists()
