"""One bounded JSON process invocation for the configured PR-review plugin."""

from __future__ import annotations

import json
import os
import re
import selectors
import signal
import subprocess
import threading
from typing import Any, Mapping

from lokay.config import Config
from lokay.pr_review_credential import resolve_pi_api_key

_MAX_INPUT_BYTES = 4 * 1024 * 1024
_MAX_OUTPUT_BYTES = 16 * 1024 * 1024
_ENV = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_ERROR_CODE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_ERROR_DETAIL = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9 _.:-]{0,199}$")
_WARNING_TYPE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_WARNING_FILE = re.compile(r"^[A-Za-z0-9_.-][A-Za-z0-9_./-]{0,254}$")
_FORBIDDEN_ENV_PREFIXES = ("GH_", "GITHUB_", "LOKAY_HEALTH_LEASE")


class PluginFailure(ValueError):
    """Sanitized plugin process failure."""

    def __init__(self, message: str = "", *, warnings: list[dict[str, str]] | None = None):
        super().__init__(message)
        self.warnings = list(warnings or [])


def _classified_error_code(decoded: Any) -> str | None:
    if not isinstance(decoded, dict):
        return None
    error = decoded.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    if not isinstance(code, str) or not _ERROR_CODE.fullmatch(code):
        return None
    return code


def _classified_error_detail(decoded: Any) -> str | None:
    if not isinstance(decoded, dict):
        return None
    error = decoded.get("error")
    if not isinstance(error, dict):
        return None
    detail = error.get("detail")
    if not isinstance(detail, str) or not _ERROR_DETAIL.fullmatch(detail):
        return None
    return detail


def _plugin_failure_message(decoded: Any, fallback: str) -> str:
    code = _classified_error_code(decoded)
    if not code:
        return fallback
    detail = _classified_error_detail(decoded)
    return f"{code}: {detail}" if detail else code


def _classified_error_warnings(decoded: Any) -> list[dict[str, str]]:
    if not isinstance(decoded, dict):
        return []
    error = decoded.get("error")
    if not isinstance(error, dict) or not isinstance(error.get("warnings"), list):
        return []
    out: list[dict[str, str]] = []
    for item in error.get("warnings")[:32]:
        if not isinstance(item, Mapping):
            continue
        type_name = str(item.get("type") or "")
        if not _WARNING_TYPE.fullmatch(type_name):
            continue
        file_name = str(item.get("file") or "")
        if file_name and (".." in file_name or not _WARNING_FILE.fullmatch(file_name)):
            file_name = ""
        out.append({"type": type_name, "file": file_name})
    return out


_HOST_FAILURE_CODES = {
    "review plugin did not return one JSON envelope": "ocr_output_not_json",
    "review plugin returned a failure status": "ocr_exited_unsuccessfully",
    "review plugin rejected the request": "ocr_exited_unsuccessfully",
    "review plugin output exceeded size limit": "ocr_output_too_large",
    "review plugin failed or timed out": "ocr_invocation_failed",
    "review plugin could not start": "ocr_invocation_failed",
    "review plugin did not consume the complete request": "ocr_invocation_failed",
    "review plugin failed to read request": "ocr_invocation_failed",
    "review plugin command and finite timeout are required": "review_timeout_invalid",
    "review request cannot be serialized": "review_result_invalid",
    "review request exceeded size limit": "ocr_output_too_large",
    "review plugin credential allowlist is invalid": "env_allowlist_forbidden",
    "review plugin provider credential is missing": "provider_credential_missing",
}


def classified_host_failure_code(message: str) -> str:
    """Map a host plugin English failure to the occupancy code."""
    return _HOST_FAILURE_CODES.get(message, message)


def _host_failure(message: str, *, warnings: list[dict[str, str]] | None = None) -> PluginFailure:
    return PluginFailure(classified_host_failure_code(message), warnings=warnings)


def _plugin_failure(decoded: Any, fallback: str) -> PluginFailure:
    return PluginFailure(
        _plugin_failure_message(decoded, classified_host_failure_code(fallback)),
        warnings=_classified_error_warnings(decoded),
    )


def _decode_plugin_envelope(output: Any, returncode: int) -> dict[str, Any]:
    if not isinstance(output, (bytes, bytearray)) or len(output) > _MAX_OUTPUT_BYTES:
        raise _host_failure("review plugin output exceeded size limit")
    try:
        decoded = json.loads(bytes(output).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _host_failure("review plugin did not return one JSON envelope") from exc
    if returncode != 0:
        raise _plugin_failure(decoded, "review plugin returned a failure status")
    if not isinstance(decoded, dict) or decoded.get("ok") is not True:
        raise _plugin_failure(decoded, "review plugin rejected the request")
    return decoded


def _plugin_env(cfg: Config) -> dict[str, str]:
    names = tuple(cfg.pr_review_provider_env)
    if len(set(names)) != len(names) or any(
        not _ENV.fullmatch(name) or name.startswith(_FORBIDDEN_ENV_PREFIXES)
        for name in names
    ):
        raise _host_failure("review plugin credential allowlist is invalid")
    values = {}
    for name in names:
        value = os.environ.get(name, "")
        if name == "OCR_LLM_API_KEY" and not value:
            try:
                value = resolve_pi_api_key()
            except Exception as exc:
                raise _host_failure("review plugin provider credential is missing") from exc
        if not value:
            raise _host_failure("review plugin provider credential is missing")
        values[name] = value
    path_dirs = ["/usr/local/bin", "/usr/bin", "/bin"]
    if os.path.sep in cfg.pr_review_plugin_command:
        path_dirs.insert(0, os.path.dirname(cfg.pr_review_plugin_command))
    return {
        "PATH": os.pathsep.join(path_dirs),
        "HOME": os.path.expanduser("~"),
        "LANG": "C.UTF-8",
        "NO_COLOR": "1",
        "TERM": "dumb",
        **values,
    }


def _read_bounded(process: subprocess.Popen[bytes], limit: int, timeout: int) -> tuple[bytes, int]:
    assert process.stdout is not None
    output = bytearray()
    deadline = __import__("time").monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - __import__("time").monotonic()
                if remaining <= 0:
                    raise _host_failure("review plugin failed or timed out")
                if not selector.select(min(remaining, 0.25)):
                    if process.poll() is not None:
                        break
                    continue
                chunk = os.read(process.stdout.fileno(), min(65536, limit + 1 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > limit:
                    raise _host_failure("review plugin output exceeded size limit")
        returncode = process.wait(timeout=max(0.1, deadline - __import__("time").monotonic()))
        return bytes(output), returncode
    except Exception:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            process.kill()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        raise


def invoke_plugin(
    cfg: Config,
    request: Mapping[str, Any],
    *,
    runner=None,
) -> dict[str, Any]:
    """Send exactly one JSON document and accept only one bounded JSON envelope."""
    command = str(cfg.pr_review_plugin_command or "").strip()
    args = list(cfg.pr_review_plugin_args or [])
    timeout = int(cfg.pr_review_plugin_timeout_seconds)
    if not command or timeout < 1:
        raise _host_failure("review plugin command and finite timeout are required")
    try:
        payload = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _host_failure("review request cannot be serialized") from exc
    if len(payload) > _MAX_INPUT_BYTES:
        raise _host_failure("review request exceeded size limit")
    env = _plugin_env(cfg)
    argv = [command, *args]
    if runner is not None:
        try:
            result = runner(argv, input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=None, env=env, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise _host_failure("review plugin failed or timed out") from exc
        output = result.stdout
        return _decode_plugin_envelope(output, result.returncode)
    else:
        try:
            process = subprocess.Popen(
                argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                env=env, start_new_session=True, bufsize=0,
            )
        except OSError as exc:
            raise _host_failure("review plugin could not start") from exc
        assert process.stdin is not None
        writer_error: list[BaseException] = []

        def write_request() -> None:
            try:
                view = memoryview(payload)
                while view:
                    written = process.stdin.write(view[:65536])
                    if not written:
                        raise BrokenPipeError("plugin closed request input")
                    view = view[written:]
            except (BrokenPipeError, OSError) as exc:
                writer_error.append(exc)
            finally:
                try:
                    process.stdin.close()
                except OSError:
                    pass

        writer = threading.Thread(target=write_request, daemon=True)
        writer.start()
        try:
            output, returncode = _read_bounded(process, _MAX_OUTPUT_BYTES, timeout)
            writer.join(timeout=1)
            if writer.is_alive():
                raise _host_failure("review plugin did not consume the complete request")
            if writer_error:
                raise _host_failure("review plugin failed to read request")
            return _decode_plugin_envelope(output, returncode)
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired, PluginFailure) as exc:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                process.kill()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            if isinstance(exc, PluginFailure):
                raise
            raise _host_failure("review plugin failed or timed out") from exc
