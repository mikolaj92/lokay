"""Run the single PR-repair agent retry after invalid JSON."""

from lokay.proc.run_coding_retry_agent import run


def execute(*, cfg, worktree, error: str, stdout: str, live: bool) -> dict:
    prompt = f"Your previous PR-repair response JSON was invalid. Return ONLY the required closed repair JSON. Validator feedback: {error}\nInvalid response: {stdout[-2000:]}"
    return run(cfg=cfg, worktree=worktree, prompt=prompt, live=live)
