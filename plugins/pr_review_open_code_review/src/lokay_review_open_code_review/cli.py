"""JSON process boundary and bounded OpenCodeReview invocation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

from .contract import ENGINE_VERSION, ContractError, normalize_result, redact_vendor_warnings, validate_request
from .background import render_background
from .tools import validate_tools
from .git_evidence import verify_checkout
from .sandbox import host_for_provider, profile_template, review_profile, validate_review_profile
from .provider_proxy import ProviderProxy

_MAX_INPUT_BYTES = 4 * 1024 * 1024
_MAX_OUTPUT_BYTES = 16 * 1024 * 1024
_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class ReviewFailure(ValueError):
    """Sanitized process boundary failure; never contains provider output."""

    def __init__(self, message: str = "", *, warnings: list[dict[str, str]] | None = None):
        super().__init__(message)
        self.warnings = redact_vendor_warnings(warnings)


_FAILURE_CODES = {
    "OpenCodeReview output exceeded size limit": "ocr_output_too_large",
    "OpenCodeReview output is not one JSON document": "ocr_output_not_json",
    "OpenCodeReview output root must be an object": "ocr_output_not_object",
    "review engine configuration missing": "review_engine_missing",
    "provider environment allowlist is required": "env_allowlist_required",
    "provider environment allowlist contains a forbidden name": "env_allowlist_forbidden",
    "OpenCodeReview version pin mismatch": "ocr_version_mismatch",
    "OpenCodeReview binary digest is required": "ocr_binary_digest_required",
    "OpenCodeReview binary digest mismatch": "ocr_binary_digest_mismatch",
    "finite positive review timeout is required": "review_timeout_invalid",
    "finite positive token budget is required": "review_budget_invalid",
    "valid review effort is required": "review_effort_invalid",
    "OS sandbox command is required": "sandbox_required",
    "OS sandbox command must end with --": "sandbox_command_invalid",
    "only the verified macOS sandbox-exec runtime is supported": "sandbox_runtime_unsupported",
    "OS sandbox command must enforce its trusted profile with -f": "sandbox_profile_flag_required",
    "isolated repository checkout is required": "checkout_required",
    "OS sandbox profile must be the trusted generated-profile template": "sandbox_profile_untrusted",
    "OS sandbox profile does not match exact checkout, scratch and provider policy": "sandbox_profile_mismatch",
    "a live exact-authority provider proxy is required": "provider_proxy_required",
    "cannot create private runtime OS sandbox profile": "sandbox_profile_create_failed",
    "trusted review configuration digest is required": "config_digest_required",
    "trusted OCR tool allowlist is invalid": "tools_allowlist_invalid",
    "allowlisted provider credential is missing": "provider_credential_missing",
    "OpenCodeReview invocation failed": "ocr_invocation_failed",
    "OpenCodeReview invocation timed out": "ocr_timed_out",
    "OpenCodeReview exited unsuccessfully": "ocr_exited_unsuccessfully",
    "review background exceeds vendor character limit": "ocr_background_too_large",
    "OpenCodeReview invocation failed or timed out": "ocr_invocation_failed",
    "trusted OpenCodeReview config is invalid": "ocr_config_invalid",
    "OpenCodeReview config must be credential-free": "ocr_config_has_credential",
    "canonical task evidence is required": "task_evidence_required",
    "review checkout evidence drifted after preview": "checkout_drift_preview",
    "review checkout evidence drifted after review": "checkout_drift_review",
    "review checkout origin does not match canonical GitHub repository": "ocr_checkout_origin_mismatch",
    "review changed-line ranges do not match exact checkout": "ocr_checkout_invalid",
    "review path inventory does not match immutable diff": "ocr_checkout_invalid",
    "review patch digest does not match exact checkout": "ocr_checkout_invalid",
    "review comparison base does not match immutable commits": "ocr_checkout_invalid",
}
_FAILURE_PREFIXES = (
    ("review engine ", "review_engine_required"),
    ("trusted ", "trusted_file_missing"),
    ("full immutable ", "immutable_sha_required"),
    ("review checkout ", "ocr_checkout_invalid"),
    ("could not ", "ocr_checkout_invalid"),
)
_CONTRACT_CAPACITY = {
    "review budget exceeded or unreported": "ocr_budget_exceeded",
    "review terminal state is not complete": "ocr_terminal_incomplete",
    "coverage is incomplete or contains non-complete states": "ocr_coverage_incomplete",
    "preview is incomplete or empty": "ocr_preview_incomplete",
}
_CONTRACT_COMPLETE_REJECT = frozenset({"review has warnings"})
_CONTRACT_PREFIX = "OpenCodeReview contract rejected: "
_DETAIL = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9 _.:-]{0,199}$")


def classified_failure_code(exc: ReviewFailure) -> str:
    message = str(exc)
    code = _FAILURE_CODES.get(message)
    if code:
        return code
    if message.startswith(_CONTRACT_PREFIX):
        detail = message[len(_CONTRACT_PREFIX):].strip()
        if detail in _CONTRACT_COMPLETE_REJECT:
            return "ocr_contract_rejected"
        return _CONTRACT_CAPACITY.get(detail, "ocr_contract_incomplete")
    for prefix, mapped in _FAILURE_PREFIXES:
        if message.startswith(prefix):
            return mapped
    return "review_failed_closed"


def classified_failure(exc: ReviewFailure) -> dict[str, Any]:
    """Code always; ContractError text only when it is a bounded ASCII detail."""
    message = str(exc)
    error: dict[str, Any] = {"code": classified_failure_code(exc)}
    if message.startswith(_CONTRACT_PREFIX):
        detail = message[len(_CONTRACT_PREFIX):].strip()
        if _DETAIL.fullmatch(detail):
            error["detail"] = detail
    warnings = list(getattr(exc, "warnings", []) or [])
    if warnings:
        error["warnings"] = warnings
    return error


def parse_one_json(raw: str | bytes, *, max_bytes: int = _MAX_OUTPUT_BYTES) -> dict[str, Any]:
    data = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(data) > max_bytes:
        raise ReviewFailure("OpenCodeReview output exceeded size limit")
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewFailure("OpenCodeReview output is not one JSON document") from exc
    if not isinstance(value, dict):
        raise ReviewFailure("OpenCodeReview output root must be an object")
    return value


def _engine(request: Mapping[str, Any]) -> Mapping[str, Any]:
    engine = request.get("engine")
    if not isinstance(engine, Mapping):
        raise ReviewFailure("review engine configuration missing")
    return engine


def _required_text(engine: Mapping[str, Any], key: str) -> str:
    value = str(engine.get(key) or "").strip()
    if not value:
        raise ReviewFailure(f"review engine {key} is required")
    return value


def _trusted_file(value: Any, name: str, *, executable: bool = False) -> str:
    path = Path(str(value or "")).expanduser().resolve()
    if not path.is_file() or not os.access(path, os.X_OK if executable else os.R_OK):
        raise ReviewFailure(f"trusted {name} file is missing or inaccessible")
    return str(path)


def _checked_env_names(engine: Mapping[str, Any]) -> tuple[str, ...]:
    raw = engine.get("env_allowlist")
    if not isinstance(raw, list):
        raise ReviewFailure("provider environment allowlist is required")
    names = tuple(str(item) for item in raw)
    forbidden = ("GH_", "GITHUB_", "LOKAY_HEALTH_LEASE")
    for name in names:
        if not _ENV_NAME.fullmatch(name) or name.startswith(forbidden):
            raise ReviewFailure("provider environment allowlist contains a forbidden name")
    return names


def build_ocr_argv(
    request: Mapping[str, Any], *, background: Path, preview: bool,
    provider_proxy_port: int | None = None,
) -> list[str]:
    engine = _engine(request)
    binary = _trusted_file(engine.get("binary_path"), "OpenCodeReview binary", executable=True)
    if engine.get("version") != ENGINE_VERSION:
        raise ReviewFailure("OpenCodeReview version pin mismatch")
    digest = str(engine.get("binary_sha256") or "").lower()
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ReviewFailure("OpenCodeReview binary digest is required")
    if hashlib.sha256(Path(binary).read_bytes()).hexdigest() != digest:
        raise ReviewFailure("OpenCodeReview binary digest mismatch")
    timeout = engine.get("timeout_minutes")
    budget = engine.get("max_tokens_budget")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1:
        raise ReviewFailure("finite positive review timeout is required")
    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 1:
        raise ReviewFailure("finite positive token budget is required")
    effort = str(engine.get("effort") or "")
    if effort not in {"low", "medium", "high"}:
        raise ReviewFailure("valid review effort is required")
    sandbox = engine.get("sandbox_command")
    if not isinstance(sandbox, list) or not sandbox or not all(str(item) for item in sandbox):
        raise ReviewFailure("OS sandbox command is required")
    sandbox_argv = [str(item) for item in sandbox]
    if sandbox_argv[-1] != "--":
        raise ReviewFailure("OS sandbox command must end with --")
    if sys.platform != "darwin":
        raise ReviewFailure("only the verified macOS sandbox-exec runtime is supported")
    _trusted_file(sandbox_argv[0], "OS sandbox executable", executable=True)
    if Path(sandbox_argv[0]).resolve() != Path("/usr/bin/sandbox-exec"):
        raise ReviewFailure("only the verified macOS sandbox-exec runtime is supported")
    template = _trusted_file(engine.get("sandbox_profile_path"), "OS sandbox profile")
    if len(sandbox_argv) < 4 or sandbox_argv[-3:-1] != ["-f", template]:
        raise ReviewFailure("OS sandbox command must enforce its trusted profile with -f")
    repo = str(request.get("repo_path") or "")
    if not repo or not Path(repo).is_dir():
        raise ReviewFailure("isolated repository checkout is required")
    if Path(template).read_text(encoding="utf-8") != profile_template():
        raise ReviewFailure("OS sandbox profile must be the trusted generated-profile template")
    scratch = background.parent.resolve()
    try:
        endpoint = host_for_provider(
            str(engine.get("provider") or ""),
            str(engine.get("provider_endpoint_url") or ""),
        )
        from .git_evidence import _git_binary, _git_runtime_paths

        git_executable = Path(_git_binary()).resolve()
        git_runtime_paths = _git_runtime_paths(git_executable)
        trusted_files = tuple(
            Path(value).resolve()
            for value in (
                engine.get("rule_path"), engine.get("tools_path"),
                engine.get("ocr_config_path"),
            )
            if value
        )
        profile_text = review_profile(
            repository=Path(repo), home=scratch, provider_endpoint_host=endpoint,
            git_executable=git_executable,
            git_runtime_paths=git_runtime_paths,
            readable_files=trusted_files,
        )
        validate_review_profile(
            profile_text,
            repository=Path(repo), home=scratch, provider_endpoint_host=endpoint,
            git_executable=git_executable,
            git_runtime_paths=git_runtime_paths,
            readable_files=trusted_files,
        )
    except ValueError as exc:
        raise ReviewFailure("OS sandbox profile does not match exact checkout, scratch and provider policy") from exc
    if provider_proxy_port is None and not preview:
        raise ReviewFailure("a live exact-authority provider proxy is required")
    sandbox_endpoint = (
        f"localhost:{provider_proxy_port}"
        if provider_proxy_port is not None
        else "localhost:" + endpoint.rsplit(":", 1)[1]
    )
    credential_runtime: tuple[Path, ...] = ()
    if str(engine.get("provider") or "") == "omniroute":
        # OCR runs api_key_cmd through macOS /bin/sh, which then execs
        # /bin/bash via /private/var/select/sh. printenv alone hangs.
        credential_runtime = (
            Path("/usr/bin/printenv"), Path("/bin/sh"), Path("/bin/bash"),
        )
    # code_search shells `git grep`, which execs /usr/bin/grep.
    # OCR itself looks up git on a /usr/bin PATH and execs that shim even
    # when evidence verification uses the Command Line Tools git.
    search_runtime = (Path("/usr/bin/git"), Path("/usr/bin/grep"))
    allowed_runtime_executables = (Path(binary), *credential_runtime, *search_runtime)
    runtime_profile_text = review_profile(
        repository=Path(repo), home=scratch,
        provider_endpoint_host=sandbox_endpoint,
        git_executable=git_executable,
        git_runtime_paths=git_runtime_paths,
        readable_files=trusted_files,
        allowed_executables=allowed_runtime_executables,
    )
    runtime_profile = scratch / "review.sb"
    try:
        if not scratch.is_dir() or scratch.stat().st_mode & 0o077:
            raise OSError("scratch directory is not private")
        if Path(repo).resolve() == scratch or Path(repo).resolve() in scratch.parents or scratch in Path(repo).resolve().parents:
            raise OSError("scratch and checkout paths must be disjoint")
        fd = os.open(runtime_profile, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(runtime_profile_text)
        runtime_profile.chmod(0o600)
    except OSError as exc:
        raise ReviewFailure("cannot create private runtime OS sandbox profile") from exc
    sandbox_argv[-2] = str(runtime_profile)
    from_sha = str(request.get("base_ref_sha") or "")
    to_sha = str(request.get("head_sha") or "")
    for name, value in (("base", from_sha), ("head", to_sha)):
        if not re.fullmatch(r"[a-fA-F0-9]{40}", value):
            raise ReviewFailure(f"full immutable {name} SHA required")
    rule = _trusted_file(engine.get("rule_path"), "review rule")
    if not re.fullmatch(r"[a-f0-9]{64}", str(engine.get("config_sha256") or "").lower()):
        raise ReviewFailure("trusted review configuration digest is required")
    argv = [*sandbox_argv, binary, "review", "--repo", repo,
            "--from", from_sha, "--to", to_sha, "--format", "json",
            "--audience", "agent", "--concurrency", "1",
            "--background-file", str(background), "--rule", rule,
            "--effort", effort, "--timeout", str(timeout),
            "--max-tokens-budget", str(budget)]
    if preview:
        argv.append("--preview")
        return argv
    tools = _trusted_file(engine.get("tools_path"), "tool allowlist")
    try:
        validate_tools(tools)
    except ValueError as exc:
        raise ReviewFailure("trusted OCR tool allowlist is invalid") from exc
    argv.extend(["--provider", _required_text(engine, "provider"),
                 "--model", _required_text(engine, "model"), "--tools", tools])
    return argv


def _contains_credential(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_name = str(key).lower()
            if key_name in {"api_key", "auth_token", "auth_token_cmd", "password", "token"}:
                return True
            if key_name == "api_key_cmd" and item != "/usr/bin/printenv OCR_LLM_API_KEY":
                return True
            if _contains_credential(item):
                return True
    elif isinstance(value, list):
        return any(_contains_credential(item) for item in value)
    return False


def _environment(engine: Mapping[str, Any], *, home: Path) -> dict[str, str]:
    names = _checked_env_names(engine)
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise ReviewFailure("allowlisted provider credential is missing")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
           "TMPDIR": str(home / "tmp"), "LANG": "C.UTF-8", "NO_COLOR": "1",
           "CLICOLOR_FORCE": "0", "FORCE_COLOR": "0", "TERM": "dumb"}
    env.update({name: os.environ[name] for name in names})
    return env


def _run_bounded(
    argv: list[str], *, cwd: Path, env: Mapping[str, str], timeout_seconds: int,
    max_bytes: int = _MAX_OUTPUT_BYTES,
) -> bytes:
    import selectors
    import time

    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        try:
            process = subprocess.Popen(
                argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=stderr_file, cwd=str(cwd), env=dict(env),
                start_new_session=True,
            )
        except OSError as exc:
            raise ReviewFailure("OpenCodeReview invocation failed") from exc
        assert process.stdout is not None
        deadline = time.monotonic() + timeout_seconds
        captured = bytearray()
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ReviewFailure("OpenCodeReview invocation timed out")
                    events = selector.select(min(remaining, 0.25))
                    if events:
                        chunk = os.read(process.stdout.fileno(), min(65536, max_bytes + 1 - len(captured)))
                        if chunk:
                            captured.extend(chunk)
                            if len(captured) > max_bytes:
                                raise ReviewFailure("OpenCodeReview output exceeded size limit")
                        elif process.poll() is not None:
                            break
                    elif process.poll() is not None:
                        chunk = os.read(process.stdout.fileno(), min(65536, max_bytes + 1 - len(captured)))
                        if chunk:
                            captured.extend(chunk)
                            if len(captured) > max_bytes:
                                raise ReviewFailure("OpenCodeReview output exceeded size limit")
                        else:
                            break
            returncode = process.wait(timeout=max(0.1, deadline - time.monotonic()))
        except Exception:
            try:
                os.killpg(process.pid, 9)
            except OSError:
                process.kill()
            process.wait()
            raise
        output = bytes(captured)
        stderr_file.seek(0)
        stderr = stderr_file.read()
        if returncode != 0:
            try:
                parse_one_json(output)
            except ReviewFailure:
                raise _ocr_exit_failure(stderr) from None
        return output


def _run_with_runner(argv, *, home, env, timeout_seconds, runner):
    try:
        completed = runner(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=str(home), env=env,
            timeout=timeout_seconds, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReviewFailure("OpenCodeReview invocation failed or timed out") from exc
    if completed.returncode != 0:
        try:
            parse_one_json(completed.stdout)
        except ReviewFailure:
            raise _ocr_exit_failure(completed.stderr) from None
    return completed.stdout


def _ocr_exit_failure(stderr: bytes | str | None) -> ReviewFailure:
    text = stderr.decode("utf-8", "replace") if isinstance(stderr, (bytes, bytearray)) else str(stderr or "")
    if "background content is" in text and "exceeding the hard limit of 8000" in text:
        return ReviewFailure("review background exceeds vendor character limit")
    return ReviewFailure("OpenCodeReview exited unsuccessfully")


def invoke_ocr(
    request: Mapping[str, Any],
    *,
    preview: bool,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    engine = _engine(request)
    timeout_minutes = engine.get("timeout_minutes")
    if not isinstance(timeout_minutes, int) or timeout_minutes < 1:
        raise ReviewFailure("finite positive review timeout is required")
    with tempfile.TemporaryDirectory(prefix="lokay-ocr-home-") as temp:
        home = Path(temp).resolve()
        (home / "tmp").mkdir()
        (home / "sessions").mkdir()
        ocr_config = home / ".opencodereview" / "config.json"
        ocr_config.parent.mkdir(mode=0o700)
        trusted_config = _trusted_file(engine.get("ocr_config_path"), "OpenCodeReview config")
        config_bytes = Path(trusted_config).read_bytes()
        try:
            config_value = json.loads(config_bytes)
        except json.JSONDecodeError as exc:
            raise ReviewFailure("trusted OpenCodeReview config is invalid") from exc
        if not isinstance(config_value, dict) or _contains_credential(config_value):
            raise ReviewFailure("OpenCodeReview config must be credential-free")
        ocr_config.write_bytes(config_bytes)
        ocr_config.chmod(0o600)
        background = home / "background.md"
        task = request.get("task")
        if not isinstance(task, Mapping):
            raise ReviewFailure("canonical task evidence is required")
        background.write_bytes(render_background(request))
        env = _environment(engine, home=home)
        env["OCR_CONFIG_DIR"] = str(home / ".opencodereview")
        if str(engine.get("provider") or "") == "openai":
            credential = env.get("OCR_LLM_API_KEY")
            if credential:
                env["OPENAI_API_KEY"] = credential
        env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": ""})
        endpoint = host_for_provider(
            str(engine.get("provider") or ""),
            str(engine.get("provider_endpoint_url") or ""),
        )
        if preview:
            output = _run_bounded(
                build_ocr_argv(request, background=background, preview=True),
                cwd=home, env=env,
                timeout_seconds=60 * timeout_minutes + 120,
            ) if runner is None else _run_with_runner(
                build_ocr_argv(request, background=background, preview=True),
                home=home, env=env, timeout_seconds=60 * timeout_minutes + 120,
                runner=runner,
            )
            return parse_one_json(output)
        with ProviderProxy(endpoint.rsplit(":", 1)[0], int(endpoint.rsplit(":", 1)[1])) as proxy:
            argv = build_ocr_argv(
                request, background=background, preview=preview,
                provider_proxy_port=proxy.port,
            )
            env.update({
                "HTTPS_PROXY": f"http://127.0.0.1:{proxy.port}",
                "HTTP_PROXY": f"http://127.0.0.1:{proxy.port}",
                "https_proxy": f"http://127.0.0.1:{proxy.port}",
                "http_proxy": f"http://127.0.0.1:{proxy.port}",
                "NO_PROXY": "localhost,127.0.0.1",
                "no_proxy": "localhost,127.0.0.1",
            })
            if runner is None:
                output = _run_bounded(
                    argv,
                    cwd=home,
                    env=env,
                    timeout_seconds=60 * timeout_minutes + 120,
                )
            else:
                output = _run_with_runner(
                    argv, home=home, env=env,
                    timeout_seconds=60 * timeout_minutes + 120, runner=runner,
                )
        return parse_one_json(output)


def scope_request(request: Mapping[str, Any]) -> dict[str, Any]:
    """One deterministic OCR call; Fala, not this plugin, starts review next."""
    from .scope import validate_scope
    try:
        validate_request(request)
        observed = verify_checkout(request)
        preview = invoke_ocr(request, preview=True)
        if verify_checkout(request) != observed:
            raise ReviewFailure("review checkout evidence drifted after preview")
        validate_scope(request, preview)
        return {
            "ok": True, "schema": "lokay.review-scope/1",
            **{key: request[key] for key in (
                "repo", "pr", "head_sha", "base_ref_sha", "comparison_base_sha",
                "diff_sha256", "task_identity_sha256", "review_config_sha256",
            )},
            "preview": preview,
        }
    except ContractError as exc:
        raise ReviewFailure(f"OpenCodeReview contract rejected: {exc}") from None


def review_request(request: Mapping[str, Any]) -> dict[str, Any]:
    engine = _engine(request)
    try:
        normalized = validate_request(request)
        repo_path = str(request.get("repo_path") or "")
        if not repo_path or not Path(repo_path).is_dir():
            raise ReviewFailure("isolated repository checkout is required")
        try:
            observed = verify_checkout(request)
        except ValueError as exc:
            raise ReviewFailure(str(exc)) from None
        request_data = dict(request)
        review_context = dict(request_data.get("engine") or {})
        request_data["engine"] = {
            **review_context,
            "ocr_config_path": review_context.get("ocr_config_path"),
        }
        from_sha, head_sha = str(request_data.get("base_ref_sha") or ""), str(request_data.get("head_sha") or "")
        request_data["review_config_sha256"] = str(engine.get("config_sha256") or "")
        request_data["repo"] = normalized["repo"]
        request_data["head_repo"] = normalized["head_repo"]
        request_data["pr"] = normalized["pr"]
        request_data["base_ref_sha"] = normalized["base_ref_sha"]
        request_data["head_sha"] = normalized["head_sha"]
        request_data["comparison_base_sha"] = normalized["comparison_base_sha"]
        request_data["diff_sha256"] = normalized["diff_sha256"]
        request_data["diff_paths"] = list(normalized["diff_paths"])
        result = invoke_ocr(request_data, preview=False)
        try:
            after_review = verify_checkout(request_data)
        except ValueError as exc:
            raise ReviewFailure(str(exc)) from None
        if after_review != observed:
            raise ReviewFailure("review checkout evidence drifted after review")
        return normalize_result(
            request,
            result,
            engine={
                "name": "open-code-review",
                "version": str(engine.get("version") or ""),
                "binary_sha256": str(engine.get("binary_sha256") or ""),
                "provider": str(engine.get("provider") or ""),
                "model": str(engine.get("model") or ""),
                "config_sha256": str(engine.get("config_sha256") or ""),
            },
            changed_ranges=request_data.get("changed_ranges") or {},
        )
    except ContractError as exc:
        raise ReviewFailure(
            f"OpenCodeReview contract rejected: {exc}",
            warnings=list(getattr(exc, "warnings", []) or []),
        ) from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-review-opencode-plugin")
    parser.add_argument("--max-input-bytes", type=int, default=_MAX_INPUT_BYTES)
    parser.add_argument("--operation", choices=("review", "scope"), default="review")
    args = parser.parse_args(argv)
    raw = sys.stdin.buffer.read(args.max_input_bytes + 1)
    if len(raw) > args.max_input_bytes:
        payload: dict[str, Any] = {"ok": False, "error": {"code": "input_too_large"}}
    else:
        try:
            request = parse_one_json(raw, max_bytes=args.max_input_bytes)
            payload = scope_request(request) if args.operation == "scope" else review_request(request)
        except ReviewFailure as exc:
            payload = {"ok": False, "error": classified_failure(exc)}
        except ValueError as exc:
            payload = {"ok": False, "error": classified_failure(ReviewFailure(str(exc)))}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
