"""Remember one test result for a head SHA and an argv."""
import json


def remember_test(cache, *, head_sha, argv, run):
    key = head_sha + "\0" + json.dumps(list(argv))
    if key in cache:
        return {**cache[key], "cached": True, "ran": False}
    result = run()
    stored = {"declared": True, "exit": result["exit"], "digest": result["digest"][:4000]}
    cache[key] = stored
    return {**stored, "cached": False, "ran": True}
