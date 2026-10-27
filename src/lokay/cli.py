from __future__ import annotations

from json import dumps

import argparse
import sys

from lokay.safety import SafetyError, validate_argv


def decide(args, rest) -> int:
    from lokay.effects.decide import main as decide_main

    if args.probe:
        sys.argv = ["lokay", "--probe"]
    return decide_main()


def start(args, rest) -> int:
    import importlib
    import pkgutil
    import lokay

    for module in pkgutil.walk_packages(lokay.__path__, lokay.__name__ + "."):
        importlib.import_module(module.name)

    from lokay.tick import main as start_main
    from lokay.observe import ticking

    if args.check:
        return start_main(["--check"])
    with ticking():
        return start_main(rest)


def dashboard(args, rest) -> int:
    from lokay.dashboard import main as dashboard_main

    sys.argv = ["lokay dashboard", *rest]
    dashboard_main()
    return 0


def refresh_body(args, rest) -> int:
    from lokay.tick import main as start_main

    return start_main(["refresh-body", *rest])


def status(args, rest) -> int:
    from lokay.observe import status

    status()
    return 0


def monitor(args, rest) -> int:
    from lokay.observe import monitor

    print(dumps(monitor()))
    return 0


def replay(args, rest) -> int:
    from lokay.replay import main as replay_main

    return replay_main(rest)


def lint(args, rest) -> int:
    from pathlib import Path
    from lokay.lint import lint

    command = argparse.ArgumentParser(prog="lokay lint")
    command.add_argument("base")
    command.add_argument("head")
    refs = command.parse_args(rest)
    try:
        errors = lint(refs.base, refs.head, Path.cwd())
    except ValueError as exc:
        print(f"lint: {exc}", file=sys.stderr)
        return 1
    for error in errors:
        print(error)
    return int(bool(errors))


def dataset(args, rest) -> int:
    from lokay.dataset import main as dataset_main

    return dataset_main(rest)


def review_b(args, rest) -> int:
    from lokay.review_b import main as review_b_main

    return review_b_main(rest)


def measure(args, rest) -> int:
    from lokay.measure import main as measure_main

    return measure_main(rest)


NODES = {
    "decide": decide,
    "start": start,
    "dashboard": dashboard,
    "refresh-body": refresh_body,
    "status": status,
    "monitor": monitor,
    "replay": replay,
    "lint": lint,
    "measure": measure,
    "dataset": dataset,
    "review-b": review_b,
}


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="lokay")
    parser.add_argument("node", nargs="?", choices=NODES)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--probe", action="store_true")
    args, rest = parser.parse_known_args(raw)
    try:
        validate_argv(["lokay", *raw])
    except SafetyError as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 2
    if args.node is None:
        parser.print_help()
        return 0
    return NODES[args.node](args, rest)


if __name__ == "__main__":
    raise SystemExit(main())
