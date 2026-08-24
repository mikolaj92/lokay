"""Read the last durable pass receipt without refreshing it."""

from pathlib import Path

from lokay.pass_receipt import read_pass_receipt


def read(config: dict) -> dict:
    receipt = read_pass_receipt(state_path=Path(config["state_path"]))
    return {"ok": True, "receipt": receipt if isinstance(receipt, dict) else None}
