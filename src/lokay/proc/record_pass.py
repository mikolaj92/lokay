"""One job: write last-pass.json receipt and emit the terminal tick envelope."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.passkit import io as pass_io
from lokay.pass_history import append_pass_receipt
from lokay.pass_receipt import build_pass_receipt, write_pass_receipt
from lokay.proc._common import add_config_live


def run_record_pass(*, pass_dir: str) -> dict[str, Any]:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    payload = pass_io.read_json(pass_io.tick_path(pass_dir))
    try:
        receipt = build_pass_receipt(
            tick=payload,
            merge_enabled=bool(begin.get("merge_enabled")),
            require_checks=bool(begin.get("require_checks")),
            require_llm_review=bool(begin.get("require_llm_review")),
            max_issue_to_pr_per_pass=int(begin.get("max_issue_to_pr_per_pass") or 0),
            config_path=begin.get("config_path"),
        )
        state_path = Path(str(begin.get("state_path")))
        written = write_pass_receipt(receipt, state_path=state_path)
        append_pass_receipt(receipt, state_path=state_path)
        payload["pass_receipt_path"] = str(written)
        pass_io.write_json(pass_io.tick_path(pass_dir), payload)
    except OSError as exc:
        payload["pass_receipt_error"] = str(exc)
        pass_io.write_json(pass_io.tick_path(pass_dir), payload)

    # Preserve complete tick envelope for the parent path normalizer. Domain
    # stall/work_remaining is successful Fala conduction with tick.ok=false.
    return ok(pass_dir=pass_dir, tick=payload, result=payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-record-pass")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(run_record_pass(pass_dir=str(args.pass_dir)))


if __name__ == "__main__":
    raise SystemExit(main())
