from __future__ import annotations

import pytest

from lokay.tool_contracts import ContractError, render_contract


def test_render_contract_loads_one_tool_contract():
    text = render_contract(
        "pr_review",
        repo="a/b",
        pr_number=7,
        head_ref="branch",
        schema="{}",
        collector_boundary="boundary",
        checks_text="green",
        title="Fix it",
        body="ticket",
        diff_text="diff",
    )
    assert "Repository: a/b" in text
    assert "PR: #7" in text
    assert "user-visible product goal" in text


def test_render_contract_rejects_missing_placeholder():
    with pytest.raises(ContractError, match="missing values"):
        render_contract("pr_review", repo="a/b")


def test_render_contract_rejects_unknown_placeholder():
    with pytest.raises(ContractError, match="unknown values"):
        render_contract(
            "pr_review",
            repo="a/b",
            pr_number=7,
            head_ref="branch",
            schema="{}",
            collector_boundary="boundary",
            checks_text="green",
            title="Fix it",
            body="ticket",
            diff_text="diff",
            surprise="no",
        )


def test_render_contract_rejects_unknown_tool():
    with pytest.raises(ContractError, match="contract not found"):
        render_contract("does_not_exist")
