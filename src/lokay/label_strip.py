"""Plan removal of control labels. Mutation happens only with apply."""
import json
import urllib.parse
import urllib.request

CONTROL = ("ai:", "work:ready")


def planned(items):
    rows = []
    for item in items:
        labels = [label for label in item.get("labels") or [] if _control(label)]
        if labels:
            rows.append({"repo": item["repo"], "number": item["number"], "kind": item["kind"], "labels": labels})
    return {"planned": rows, "applied": False}


def apply_plan(plan, *, token, endpoint="https://api.github.com"):
    for row in plan["planned"]:
        owner, repo = row["repo"].split("/", 1)
        for label in row["labels"]:
            name = urllib.parse.quote(label, safe="")
            url = f"{endpoint}/repos/{owner}/{repo}/issues/{row['number']}/labels/{name}"
            request = urllib.request.Request(url, method="DELETE", headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(request) as response:
                response.read()
    return {"planned": plan["planned"], "applied": True}


def main(argv):
    import argparse
    parser = argparse.ArgumentParser(prog="lokay labels strip")
    parser.add_argument("--repo")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("items")
    args = parser.parse_args(argv)
    items = json.loads(open(args.items, encoding="utf-8").read())
    if args.repo:
        items = [item for item in items if item.get("repo") == args.repo]
    plan = planned(items)
    if args.apply:
        import os
        plan = apply_plan(plan, token=os.environ["GH_TOKEN"])
    print(json.dumps(plan, ensure_ascii=False))
    return 0


def _control(label):
    return label == "work:ready" or label.startswith("ai:")
