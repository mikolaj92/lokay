"""The repair seat must advertise JSON the actual admission gate accepts."""
import json
import re
from importlib.resources import files

import pytest

from lokay.repair_boundary import VERDICTS, validate_output


@pytest.mark.parametrize("tool", ["pr_repair", "evidence_repair", "pr_test_repair"])
def test_repair_prompt_terminal_example_passes_real_validator(tool):
    prompt = files("lokay").joinpath("tool_contracts", tool, "prompt.md").read_text()
    examples = []
    for line in prompt.splitlines():
        try:
            examples.append(json.loads(line))
        except ValueError:
            continue
    repaired = [row for row in examples if row.get("verdict") == "repaired"]
    assert repaired, "provide a literal valid terminal JSON, not a union masquerading as JSON"
    for example in repaired:
        assert validate_output(json.dumps(example))["route"] == "valid"
        assert example["evidence_kind"] is None
    assert "needs_human" not in prompt
    advertised = re.search(r'"verdict":([^,]+)', prompt)
    assert advertised
    assert set(re.findall(r'"([a-z_]+)"', advertised[1])) <= VERDICTS


def test_repaired_cannot_mislabel_consumed_evidence_as_a_new_request():
    result = {"verdict": "repaired", "evidence_kind": "review_findings",
              "summary": "README repaired", "tests_run": ["pytest"], "residual_risk": ""}
    assert validate_output(json.dumps(result))["route"] == "retry"
    result["evidence_kind"] = None
    assert validate_output(json.dumps(result))["route"] == "valid"
