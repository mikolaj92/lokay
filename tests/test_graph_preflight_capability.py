import os

import fala
import pytest

from lokay import graph_run, preflight


class HostReached(Exception):
    pass


@pytest.mark.parametrize("already_inherited", [False, True])
def test_graph_passes_validated_capability_to_host(tmp_path, monkeypatch, already_inherited):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "")
    issued = {}

    def verified_preflight(config_path):
        lock = tmp_path / ".lokay" / "lokay.lock"
        lock.parent.mkdir(exist_ok=True)
        assert preflight.acquire_run_lock(lock)
        preflight.issue_health_lease(lock_path=lock)
        issued["token"] = os.environ["LOKAY_HEALTH_LEASE"]
        assert preflight.health_lease_status(lock_path=lock) == (True, "ok")

    def inspect_host(**kwargs):
        assert os.environ["LOKAY_HEALTH_LEASE"] == issued["token"]
        assert preflight.health_lease_status() == (True, "ok")
        raise HostReached

    if already_inherited:
        verified_preflight(None)
    monkeypatch.setattr(preflight, "require_healthy", verified_preflight)
    monkeypatch.setattr(fala, "host_run_package", inspect_host)
    with pytest.raises(HostReached):
        graph_run.run_path(path_id="pr_triage", repo="owner/product", pr=219,
                           branch="ai/fix/161", live=True, db_path=tmp_path / "journal")
