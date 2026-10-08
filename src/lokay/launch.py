"""Launch command for one blueprint run. Not executed here."""


def launch(candidate, *, token, seq, gb10_up=True):
    if not gb10_up:
        return {"launched": []}
    argv = [
        "setsid", "lokay", "blueprint",
        "--work-id", candidate["work_id"],
        "--mode", candidate["mode"],
        "--token", str(token),
        "--seq", str(seq),
    ]
    return {"launched": [{"work_id": candidate["work_id"], "argv": argv}]}
