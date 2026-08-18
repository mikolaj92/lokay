import json
from pathlib import Path
from types import SimpleNamespace

from lokay.proc import self_repair_push_main


def result(argv, *, returncode=0, stdout="", stderr=""):
    return SimpleNamespace(
        spec=SimpleNamespace(argv=tuple(argv)),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class FakeRunner:
    def __init__(self, remote="b" * 40, head="f" * 40):
        self.remote = remote
        self.head = head
        self.calls = []

    def run_checked(self, spec, *, live):
        self.calls.append(list(spec.argv))
        if spec.argv[1:3] == ("rev-parse", "origin/main"):
            return result(spec.argv, stdout=self.remote + "\n")
        if spec.argv[1:3] == ("rev-parse", "HEAD"):
            return result(spec.argv, stdout=self.head + "\n")
        return result(spec.argv)


def invoke(monkeypatch, tmp_path, fake, *, base="b" * 40, expected="f" * 40):
    monkeypatch.setattr(self_repair_push_main, "load_cfg", lambda a: SimpleNamespace())
    monkeypatch.setattr(self_repair_push_main, "mutations_allowed", lambda **k: True)
    monkeypatch.setattr(self_repair_push_main, "runner", lambda: fake)
    return self_repair_push_main.main([
        "--config", str(tmp_path / "config.yaml"), "--live",
        "--worktree", str(tmp_path), "--base-sha", base, "--validated",
        "--expected-commit", expected,
    ])


def payload(capsys):
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_push_main_is_exact_non_force_refspec(monkeypatch, tmp_path, capsys):
    fake = FakeRunner()
    assert invoke(monkeypatch, tmp_path, fake) == 0
    out = payload(capsys)
    assert out["pushed"] is True and out["commit"] == "f" * 40
    push = next(call for call in fake.calls if call[1] == "push")
    assert push == ["git", "push", "origin", f"{'f' * 40}:refs/heads/main"]
    assert all("force" not in arg for arg in push)


def test_push_main_rejects_changed_origin(monkeypatch, tmp_path, capsys):
    fake = FakeRunner(remote="a" * 40)
    assert invoke(monkeypatch, tmp_path, fake) == 1
    assert "origin/main changed" in payload(capsys)["error"]
    assert not any(call[1] == "push" for call in fake.calls)


def test_push_main_rejects_no_commit(monkeypatch, tmp_path, capsys):
    fake = FakeRunner(head="b" * 40)
    assert invoke(monkeypatch, tmp_path, fake) == 1
    assert "no commit" in payload(capsys)["error"]
    assert not any(call[1] == "push" for call in fake.calls)


def test_push_main_rejects_candidate_changed_after_validation(
    monkeypatch, tmp_path, capsys
):
    fake = FakeRunner(head="c" * 40)
    assert invoke(monkeypatch, tmp_path, fake, expected="d" * 40) == 1
    assert "candidate changed" in payload(capsys)["error"]
    assert not any(call[1] == "push" for call in fake.calls)


def test_push_rejects_empty_expected_commit(tmp_path, monkeypatch, capsys):
    fake = FakeRunner()
    monkeypatch.setattr(self_repair_push_main, "load_cfg", lambda _args: SimpleNamespace())
    monkeypatch.setattr(
        self_repair_push_main,
        "mutations_allowed",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(self_repair_push_main, "runner", lambda: fake)

    code = self_repair_push_main.main(
        [
            "--live",
            "--worktree",
            str(tmp_path),
            "--base-sha",
            "base",
            "--validated",
            "--expected-commit",
            "",
        ]
    )

    assert code == 1
    assert "expected commit is invalid" in capsys.readouterr().out
    assert fake.calls == []
