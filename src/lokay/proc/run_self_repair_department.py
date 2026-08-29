"""Parent slot: child Fala self_repair_department (incident + existing self_repair)."""

from lokay.graph_run import run_path


def run(*, config_path: str | None = None) -> dict:
    return run_path(
        path_id="self_repair_department",
        repo="__self_repair_department__",
        config_path=config_path,
        live=True,
        require_healthy=False,
        extra_inputs={"config_path": config_path or ""},
    )
