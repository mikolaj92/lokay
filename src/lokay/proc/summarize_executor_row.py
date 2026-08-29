"""Receipt for one executor row: do becomes an open PR. No merge here."""

from lokay.proc.summarize_issues import summarize as write_row


def summarize(picked: dict, do: dict, launched: dict, *, pass_dir: str = "") -> dict:
    return write_row(picked, do, launched, pass_dir=pass_dir)
