"""Read the durable issue-delivery projection without changing it."""

from pathlib import Path

from lokay.work_units import project_work_units, status_work_units


def read(config: dict) -> dict:
    visible, latest = status_work_units(
        project_work_units(Path(config["state_path"]))
    )
    return {"ok": True, "work_units": visible, "latest_delivery": latest}
