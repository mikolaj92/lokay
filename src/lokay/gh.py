"""Blueprint GitHub writes. Labels and assignment are not in this surface."""
WRITES = ("pr_upsert", "pr_ready", "review_comment", "verdict_status")
FORBIDDEN = ("ensure_labels", "assign_issue", "--label", "--add-label")


def pr_upsert(repo, head, title, body):
    return ["pr", "create", "--repo", repo, "--head", head, "--title", title, "--body", body, "--draft"]


def pr_ready(repo, number):
    return ["pr", "ready", "--repo", repo, str(number)]


def review_comment(repo, number, body):
    return ["pr", "comment", "--repo", repo, str(number), "--body", body]


def verdict_status(repo, sha, state):
    return ["api", f"repos/{repo}/statuses/{sha}", "-f", f"state={state}", "-f", "context=lokay/verdict"]
