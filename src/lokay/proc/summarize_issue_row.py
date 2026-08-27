"""Receipt for one issue_row. Two small functions: envelope, then write."""

from lokay.proc.summarize_issues import envelope, summarize as write_row


def summarize(
    picked: dict,
    do: dict,
    launched: dict,
    *,
    pass_dir: str = "",
) -> dict:
    return write_row(picked, do, launched, pass_dir=pass_dir)


def from_row(picked: dict, do: dict, launched: dict) -> dict:
    return envelope(picked, do, launched)
