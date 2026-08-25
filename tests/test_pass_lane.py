"""Oil XOR product: product wins when any product candidate exists."""

from lokay.proc.pass_lane import classify_pass_lane, product_candidates, self_repo


def test_self_repo_reads_config_then_default() -> None:
    assert self_repo({"incident_repo": "owner/self"}) == "owner/self"
    assert self_repo({}) == "mikolaj92/lokay"


def test_product_candidates_from_ready_or_pr() -> None:
    self_id = "mikolaj92/lokay"
    assert (
        product_candidates(
            ready_by_repo={"a/b": [{"number": 1}]},
            prs_by_repo={self_id: [{"number": 2, "headRefName": "ai/fix/1"}]},
            self_id=self_id,
        )
        is True
    )
    assert (
        product_candidates(
            ready_by_repo={self_id: [{"number": 1}]},
            prs_by_repo={self_id: [{"number": 2, "headRefName": "ai/fix/1"}]},
            self_id=self_id,
        )
        is False
    )


def test_lane_product_oil_idle() -> None:
    self_id = "mikolaj92/lokay"
    assert (
        classify_pass_lane(
            self_id=self_id,
            ready_by_repo={"a/b": [{"number": 1}], self_id: [{"number": 2}]},
            selected_repo="a/b",
        )
        == "product"
    )
    assert (
        classify_pass_lane(
            self_id=self_id,
            ready_by_repo={self_id: [{"number": 2}]},
            selected_repo=self_id,
        )
        == "oil"
    )
    assert classify_pass_lane(self_id=self_id) == "idle"
