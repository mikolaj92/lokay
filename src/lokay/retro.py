import gzip
import hashlib
import json
import re

from lokay import store
from lokay.effects.gh import gh_json, gh_ok, fit_body
from lokay.replay import unpack
from lokay.types import Finding, parse_finding, pr_number


CATEGORIES = frozenset(("logic bug", "missing handling/validation", "wrong scope (unrelated change)",
                        "security", "docs/plan only instead of code"))


def proposals(directory):
    groups = {}
    for path in sorted((*directory.glob("*.jsonl"), *directory.glob("*.jsonl.gz"))):
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt") as stream:
            for line in stream:
                row = json.loads(line)
                repo, issue = row.get("repo"), row.get("issue")
                if (row.get("kind") != "transition" or not isinstance(repo, str)
                        or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo)
                        or type(issue) is not int or issue < 1):
                    continue
                state = unpack(row.get("after"), directory.parent, source=directory)
                if not isinstance(state, dict):
                    continue
                verdict = state.get("last_check") or state.get("verdict") or {}
                sha, pr = verdict.get("sha"), pr_number(state.get("pr"))
                if (not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha)
                        or state.get("sha") != sha or type(pr) is not int or pr < 1):
                    continue
                for finding in verdict.get("uwagi") or []:
                    item = parse_finding(finding)
                    if not isinstance(item, Finding):
                        continue
                    category = item.zmiana
                    lens, quote = item.lens, finding.get("uzasadnienie")
                    if (not isinstance(category, str) or category not in CATEGORIES
                            or not isinstance(lens, str) or not lens.strip()
                            or not isinstance(quote, str) or not quote.strip()):
                        continue
                    groups.setdefault((lens, category), {}).setdefault((repo, issue),
                        f"- https://github.com/{repo}/issues/{issue} · "
                        f"https://github.com/{repo}/pull/{pr} · SHA `{sha}`\n\n"
                        + "\n".join("> " + text for text in quote.splitlines()))
    return {key: evidence for key, evidence in groups.items() if len(evidence) >= 3}


def publish():
    directory = store.RUNS.parent / "ticks"
    with store.shared_file_lock(store.RUNS.parent / "retro.lock"):
        for (lens, category), evidence in sorted(proposals(directory).items()):
            marker = "Lokay retro: " + hashlib.sha256(json.dumps(
                [lens, category], ensure_ascii=False).encode()).hexdigest()
            rows = gh_json(["issue", "list", "--repo", "mikolaj92/lokay", "--state", "all",
                            "--limit", "1000000", "--json", "number,body"], error="retro lookup failed")
            if (not isinstance(rows, list) or any(not isinstance(row, dict)
                    or type(row.get("number")) is not int or not isinstance(row.get("body"), str)
                    for row in rows)):
                raise RuntimeError("invalid retro lookup")
            if any(marker in row["body"].splitlines() for row in rows):
                continue
            body = marker + f"\n\nLens: {lens}\nCategory: {category}\n\n" + "\n\n".join(
                evidence[key] for key in sorted(evidence)[:3])
            if fit_body(body) != body:
                continue
            gh_ok(["issue", "create", "--repo", "mikolaj92/lokay", "--title",
                   "nowy check w checks.py: " + category, "--body", body], error="retro creation failed")
