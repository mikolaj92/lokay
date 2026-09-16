from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _bounded_runner(argv, **kwargs):
    from lokay.pr_review_credential import _run_resolver

    return subprocess.CompletedProcess(
        argv,
        0,
        stdout=_run_resolver(
            argv,
            environment=kwargs["env"],
            timeout=kwargs.get("timeout", 10),
        ),
    )


def test_pi_resolver_uses_a_minimal_environment_and_strips_one_final_newline(
    tmp_path: Path,
):
    from lokay.pr_review_credential import resolve_pi_api_key

    observed = tmp_path / "environment.json"
    script = tmp_path / "resolver.py"
    script.write_text(
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(sys.argv[1]).write_text(json.dumps(dict(os.environ)))\n"
        "sys.stdout.write('resolved-review-key\\n')\n",
        encoding="utf-8",
    )

    resolved = resolve_pi_api_key(
        command=(sys.executable, str(script), str(observed)),
        home=tmp_path,
        runner=_bounded_runner,
    )

    assert resolved == "resolved-review-key"
    environment = json.loads(observed.read_text(encoding="utf-8"))
    assert environment["HOME"] == str(tmp_path)
    assert environment["LANG"] == "C.UTF-8"
    assert environment["NO_COLOR"] == "1"
    assert environment["TERM"] == "dumb"
    assert set(environment) <= {
        "HOME", "PATH", "LANG", "NO_COLOR", "TERM", "__CF_USER_TEXT_ENCODING"
    }
    assert "OCR_LLM_API_KEY" not in environment
    assert "OPENAI_API_KEY" not in environment
    assert "GH_TOKEN" not in environment
    assert "GITHUB_TOKEN" not in environment
    assert "LOKAY_HEALTH_LEASE" not in environment
    assert "resolved-review-key" not in os.environ.values()


def test_pi_resolver_rejects_multiline_and_resolver_failure_without_leaking_output(
    tmp_path: Path,
):
    from lokay.pr_review_credential import PiCredentialError, resolve_pi_api_key

    script = tmp_path / "resolver.py"
    script.write_text(
        "import sys\n"
        "if sys.argv[1] == 'multiline':\n"
        "    sys.stdout.buffer.write(b'key\\nextra\\n')\n"
        "else:\n"
        "    sys.stderr.write('sensitive resolver diagnostic')\n"
        "    raise SystemExit(17)\n",
        encoding="utf-8",
    )

    with pytest.raises(PiCredentialError, match="invalid output"):
        resolve_pi_api_key(
            command=(sys.executable, str(script), "multiline"),
            home=tmp_path,
            runner=_bounded_runner,
        )
    with pytest.raises(PiCredentialError, match="resolver failed") as caught:
        resolve_pi_api_key(
            command=(sys.executable, str(script), "failed"),
            home=tmp_path,
            runner=_bounded_runner,
        )
    assert "sensitive resolver diagnostic" not in str(caught.value)


def test_pi_resolver_does_not_accept_a_second_trailing_newline(tmp_path: Path):
    from lokay.pr_review_credential import PiCredentialError, resolve_pi_api_key

    script = tmp_path / "resolver.py"
    script.write_text(
        "import sys\n"
        "sys.stdout.buffer.write(b'key\\n\\n')\n",
        encoding="utf-8",
    )

    with pytest.raises(PiCredentialError, match="invalid output"):
        resolve_pi_api_key(command=(sys.executable, str(script)), home=tmp_path, runner=_bounded_runner)


def test_pi_resolver_accepts_one_crlf_but_not_bare_cr(tmp_path: Path):
    from lokay.pr_review_credential import PiCredentialError, resolve_pi_api_key

    script = tmp_path / "resolver.py"
    script.write_text(
        "import sys\n"
        "sys.stdout.buffer.write(b'key\\r\\n' if sys.argv[1] == 'crlf' else b'key\\r')\n",
        encoding="utf-8",
    )

    assert resolve_pi_api_key(
        command=(sys.executable, str(script), "crlf"), home=tmp_path, runner=_bounded_runner
    ) == "key"
    with pytest.raises(PiCredentialError, match="invalid output"):
        resolve_pi_api_key(command=(sys.executable, str(script), "cr"), home=tmp_path, runner=_bounded_runner)


def test_pi_resolver_rejects_nul_output(tmp_path: Path):
    from lokay.pr_review_credential import PiCredentialError, resolve_pi_api_key

    script = tmp_path / "resolver.py"
    script.write_text(
        "import sys\n"
        "sys.stdout.buffer.write(b'key\\x00')\n",
        encoding="utf-8",
    )

    with pytest.raises(PiCredentialError, match="invalid output"):
        resolve_pi_api_key(command=(sys.executable, str(script)), home=tmp_path, runner=_bounded_runner)


def test_pi_resolver_uses_the_default_command_factory_for_production(monkeypatch):
    from lokay.pr_review_credential import PiCredentialError, resolve_pi_api_key

    monkeypatch.setattr(
        "lokay.pr_review_credential.default_resolver_command",
        lambda: ("/trusted/pi", "auth", "print-api-key", "--provider", "omniroute"),
    )
    monkeypatch.setattr(
        "lokay.pr_review_credential.resolver_command_is_canonical",
        lambda command: tuple(command) == ("/trusted/pi", "auth", "print-api-key", "--provider", "omniroute"),
    )
    with pytest.raises(PiCredentialError, match="failed"):
        resolve_pi_api_key()


def test_pi_resolver_rejects_noncanonical_command_without_runner(tmp_path: Path):
    from lokay.pr_review_credential import PiCredentialError, resolve_pi_api_key

    with pytest.raises(PiCredentialError, match="canonical"):
        resolve_pi_api_key(command=(sys.executable, "-c", "print('key')"))


def test_pi_resolver_rejects_invalid_command_arguments(tmp_path: Path):
    from lokay.pr_review_credential import PiCredentialError, resolve_pi_api_key

    with pytest.raises(PiCredentialError, match="command is invalid"):
        resolve_pi_api_key(command=(sys.executable, ""), home=tmp_path)
    with pytest.raises(PiCredentialError, match="command is invalid"):
        resolve_pi_api_key(command=(sys.executable, "bad\narg"), home=tmp_path)
    with pytest.raises(PiCredentialError, match="command is invalid"):
        resolve_pi_api_key(command=(sys.executable, "bad\x00arg"), home=tmp_path)


def test_pi_resolver_uses_real_home_by_default(monkeypatch, tmp_path: Path):
    from lokay.pr_review_credential import resolve_pi_api_key

    observed = tmp_path / "home.txt"

    def runner(argv, **kwargs):
        observed.write_text(kwargs["env"]["HOME"], encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": b"key"})()

    monkeypatch.setattr("lokay.pr_review_credential.resolver_home", lambda: tmp_path / "real-pi-home")
    monkeypatch.setattr("lokay.pr_review_credential.resolver_command_is_canonical", lambda _command: False)
    assert resolve_pi_api_key(
        command=("/trusted/pi", "auth", "print-api-key", "--provider", "omniroute"),
        runner=runner,
    ) == "key"
    assert observed.read_text(encoding="utf-8") == str(tmp_path / "real-pi-home")


def test_pi_resolver_uses_direct_argv_and_devnull_stdin(tmp_path: Path):
    from lokay.pr_review_credential import resolve_pi_api_key

    observed = tmp_path / "invocation.json"
    script = tmp_path / "resolver.py"
    script.write_text(
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(sys.argv[1]).write_text(json.dumps({'argv': sys.argv[2:], 'stdin_tty': os.isatty(0)}))\n"
        "sys.stdout.write('resolved-review-key')\n",
        encoding="utf-8",
    )

    assert resolve_pi_api_key(
        command=(sys.executable, str(script), str(observed), "literal;not-shell"),
        home=tmp_path,
        runner=_bounded_runner,
    ) == "resolved-review-key"
    invocation = json.loads(observed.read_text(encoding="utf-8"))
    assert invocation == {"argv": ["literal;not-shell"], "stdin_tty": False}


def test_pi_resolver_rejects_whitespace_and_non_utf8_output(tmp_path: Path):
    from lokay.pr_review_credential import PiCredentialError, resolve_pi_api_key

    script = tmp_path / "resolver.py"
    script.write_text(
        "import sys\n"
        "sys.stdout.buffer.write(b'   \\n') if sys.argv[1] == 'space' else sys.stdout.buffer.write(b'\\xff\\n')\n",
        encoding="utf-8",
    )

    for kind in ("space", "bytes"):
        with pytest.raises(PiCredentialError, match="invalid output"):
            resolve_pi_api_key(
                command=(sys.executable, str(script), kind),
                home=tmp_path,
                runner=_bounded_runner,
            )


def test_pi_resolver_rejects_empty_output(tmp_path: Path):
    from lokay.pr_review_credential import PiCredentialError, resolve_pi_api_key

    script = tmp_path / "resolver.py"
    script.write_text("raise SystemExit(0)\n", encoding="utf-8")

    with pytest.raises(PiCredentialError, match="invalid output"):
        resolve_pi_api_key(command=(sys.executable, str(script)), home=tmp_path, runner=_bounded_runner)


def test_pi_resolver_rejects_timeout_without_exposing_diagnostics(tmp_path: Path):
    from lokay.pr_review_credential import PiCredentialError, resolve_pi_api_key

    script = tmp_path / "resolver.py"
    script.write_text(
        "import sys, time\n"
        "sys.stderr.write('secret timeout diagnostic')\n"
        "sys.stderr.flush()\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )

    with pytest.raises(PiCredentialError, match="timed out") as caught:
        resolve_pi_api_key(command=(sys.executable, str(script)), home=tmp_path, runner=_bounded_runner)
    assert "secret timeout diagnostic" not in str(caught.value)


def test_pi_resolver_bounds_stdout_before_waiting_for_the_child(tmp_path: Path):
    from lokay.pr_review_credential import PiCredentialError, resolve_pi_api_key

    script = tmp_path / "resolver.py"
    script.write_text(
        "import sys, time\n"
        "sys.stdout.buffer.write(b'x' * 5000)\n"
        "sys.stdout.flush()\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )

    with pytest.raises(PiCredentialError, match="size limit"):
        resolve_pi_api_key(
            command=(sys.executable, str(script)),
            home=tmp_path,
            runner=_bounded_runner,
        )
