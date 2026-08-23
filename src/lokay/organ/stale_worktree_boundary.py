"""Fala bindings for bounded stale-worktree hygiene."""

from typing import Any


def handle_stale_worktree(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    if atom == "collect_stale_worktree_candidates":
        from lokay.proc.collect_stale_worktree_candidates import collect

        return collect(
            pass_dir=str(inputs.get("pass_dir") or ""),
            config_path=str(inputs.get("config_path") or "") or None,
        )
    if atom.startswith("classify_stale_worktree_"):
        from lokay.proc.classify_stale_worktree_candidate import classify

        slot = int(atom.rsplit("_", 1)[-1])
        candidate = dict(
            (up.get("collect_stale_worktree_candidates") or {}).get(f"candidate_{slot}")
            or {}
        )
        return classify(candidate, live=bool(inputs.get("live")))
    if atom.startswith("keep_stale_worktree_"):
        from lokay.proc.keep_stale_worktree_candidate import apply

        slot = atom.rsplit("_", 1)[-1]
        return apply(up.get(f"classify_stale_worktree_{slot}") or {})
    if atom.startswith("remove_stale_worktree_"):
        from lokay.proc.remove_stale_worktree_candidate import apply

        slot = atom.rsplit("_", 1)[-1]
        return apply(
            up.get(f"classify_stale_worktree_{slot}") or {},
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )
    if atom == "summarize_stale_worktree_reap":
        from lokay.proc.summarize_stale_worktree_reap import summarize

        effects = []
        for slot in range(1, 5):
            effects.extend(
                [
                    up.get(f"keep_stale_worktree_{slot}") or {},
                    up.get(f"remove_stale_worktree_{slot}") or {},
                ]
            )
        return summarize(
            pass_dir=str(inputs.get("pass_dir") or ""),
            collected=up.get("collect_stale_worktree_candidates") or {},
            effects=effects,
        )
    return None
