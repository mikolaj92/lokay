"""Update the empty-probe stamp after complete reduction."""

from pathlib import Path
from lokay.proc.stale_implementing_stamp import clear_stale_stamp, touch_stale_stamp


def update(reduced: dict) -> dict:
    stamp = Path(reduced["stamp"]) if reduced.get("stamp") else None
    if reduced.get("probed") and not reduced.get("probe_failed"):
        if reduced.get("reaped") and reduced.get("apply"):
            clear_stale_stamp(stamp)
        elif not reduced.get("reaped"):
            touch_stale_stamp(stamp)
    return {**reduced, "ok": True}
