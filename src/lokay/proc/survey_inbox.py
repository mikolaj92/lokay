"""CLI facade for authored catalog inbox survey."""

import argparse
from lokay.envelope import emit_exit, err
from lokay.proc._common import add_config_live

MINI_MILL_REPO = "mikolaj92/lokay"


def run_survey_inbox(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    from lokay.proc.survey_inbox_subflow import run

    return run(pass_dir=pass_dir, config_path=config_path, live=live)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lokay-survey-inbox")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_survey_inbox(
            pass_dir=args.pass_dir, config_path=args.config, live=bool(args.live)
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
