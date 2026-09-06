"""An unselected Fala recheck is absent evidence, not a red test."""

import pytest

from lokay.organ.common import _require_test_local


@pytest.mark.parametrize("passed", [True, False])
def test_unselected_recheck_uses_first_test_result(passed):
    refused = _require_test_local({
        "test_local": {"ok": True, "tested": True, "passed": passed},
        "test_local_recheck": {
            "reason": "condition_not_met",
            "when": {"equals": "repaired", "path": "route",
                     "upstream": "select_test_repair_result"},
        },
    })
    if passed:
        assert refused is None
    else:
        assert refused is not None
        assert refused["reason"] == "test_local_failed"


def test_actual_failed_recheck_still_blocks_green_first_test():
    refused = _require_test_local({
        "test_local": {"ok": True, "tested": True, "passed": True},
        "test_local_recheck": {"ok": False, "passed": False},
    })
    assert refused is not None
    assert refused["reason"] == "test_local_recheck_failed"
