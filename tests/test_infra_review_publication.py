"""An infrastructure review miss is not a product verdict."""

from lokay.pr_review import parse_review_markers
from lokay.pr_review_io import publish_fail_closed


class _Runner:
    def run(self, argv, **kwargs):
        return type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()


def test_infrastructure_failure_posts_no_marker_and_no_label(monkeypatch):
    published = {}

    def publish_review(_runner, repo, pr, body, labels, *, live):
        published.update(repo=repo, pr=pr, body=body, labels=labels, live=live)

    monkeypatch.setattr("lokay.pr_review_io.publish_review", publish_review)
    applied = publish_fail_closed(
        _Runner(),
        "o/r",
        7,
        RuntimeError("tools_allowlist_invalid"),
        mutate=True,
        head_sha="a" * 40,
        comments=["<!-- lokay-review head=%s verdict=fail_closed merge_ok=0 -->" % ("b" * 40)],
    )

    assert applied is True
    assert published["labels"] == []
    assert "infrastructure, not a product verdict" in published["body"]
    assert "tools_allowlist_invalid" in published["body"]
    assert parse_review_markers([published["body"]]) == []


def test_infrastructure_failure_does_not_publish_when_mutations_are_off():
    assert publish_fail_closed(
        _Runner(), "o/r", 7, RuntimeError("plugin down"), mutate=False
    ) is False
