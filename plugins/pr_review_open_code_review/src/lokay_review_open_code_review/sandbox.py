"""Derive and validate a fail-closed macOS sandbox profile for one review."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit


def _host_port(value: str) -> str:
    text = str(value or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9.-]+:[0-9]{1,5}", text):
        raise ValueError("provider endpoint must be a host:port")
    host, port = text.rsplit(":", 1)
    if not host or int(port) < 1 or int(port) > 65535:
        raise ValueError("provider endpoint must be a valid host:port")
    return f"{host}:{port}"


def profile_template() -> str:
    return "lokay-review-sandbox-profile/1\n"


def host_for_provider(provider: str, endpoint: str = "") -> str:
    """Resolve one explicit OCR provider to its pinned default endpoint host."""
    defaults = {
        "anthropic": "https://api.anthropic.com",
        "openai": "https://api.openai.com/v1",
        "openai-responses": "https://api.openai.com/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
        "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "dashscope-tokenplan": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
        "deepseek": "https://api.deepseek.com",
        "tencent-tokenhub": "https://tokenhub.tencentmaas.com/v1",
        "hy-tokenplan": "https://api.lkeap.cloud.tencent.com/plan/v3",
        "iflytek": "https://spark-api-open.xf-yun.com/v1",
        "kimi": "https://api.moonshot.cn/v1",
        "kimi-global": "https://api.moonshot.ai/v1",
        "z-ai": "https://open.bigmodel.cn/api/paas/v4",
        "mimo": "https://api.xiaomimimo.com/v1",
        "minimax": "https://api.minimax.io/v1",
        "minimax-cn": "https://api.minimaxi.com/v1",
        "baidu-qianfan": "https://qianfan.baidubce.com/v2",
        "siliconflow": "https://api.siliconflow.com/v1",
        "siliconflow-cn": "https://api.siliconflow.cn/v1",
        "novita": "https://api.novita.ai/openai",
        "xai": "https://api.x.ai/v1",
    }
    raw = endpoint or defaults.get(provider, "")
    parsed = urlsplit(raw)
    if (
        parsed.scheme != "https" or not parsed.hostname
        or parsed.username or parsed.password or parsed.query or parsed.fragment
    ):
        raise ValueError("provider endpoint must be a trusted HTTPS URL without credentials")
    port = parsed.port or 443
    return _host_port(f"{parsed.hostname}:{port}")


def _sandbox_path(path: Path) -> str:
    # macOS exposes /var/folders through /private/var/folders to sandboxd.
    value = str(path.resolve())
    if value.startswith("/var/"):
        value = "/private" + value
    return value


def review_profile(
    *, repository: Path, home: Path, provider_endpoint_host: str,
    git_executable: Path | str = "/usr/bin/git",
    git_runtime_paths: tuple[Path | str, ...] = (),
    readable_files: tuple[Path | str, ...] = (),
    allowed_executables: tuple[Path | str, ...] = (),
) -> str:
    repo = _sandbox_path(repository)
    scratch = _sandbox_path(home)
    endpoint = _host_port(provider_endpoint_host)
    git = Path(git_executable).resolve()
    executables = sorted({git, *(Path(item).resolve() for item in allowed_executables)})
    git_runtime = sorted({_sandbox_path(Path(item)) for item in git_runtime_paths})
    readable = sorted({_sandbox_path(Path(item)) for item in readable_files})
    readable_ancestors = sorted({_sandbox_path(Path(item).resolve().parent) for item in readable_files})
    repo_resolved = Path(repository).resolve()
    repo_ancestors = _sandbox_path(repo_resolved.parent)
    repo_parent_ancestors = _sandbox_path(repo_resolved.parent.parent.parent)
    scratch_ancestors = _sandbox_path(Path(home).resolve().parent)
    return "\n".join([
        "(version 1)",
        "(deny default)",
        '(import "system.sb")',
        *(f'(allow process-exec (literal "{item}"))' for item in executables),
        '(allow file-read* (subpath "/System"))',
        '(allow file-read* (subpath "/usr"))',
        '(allow file-read* (subpath "/Library/Developer"))',
        '(allow file-read-metadata file-test-existence (subpath "/Users"))',
        '(allow file-read* (literal "/var/select/developer_dir"))',
        '(allow file-read* (literal "/private/var/select/developer_dir"))',
        '(allow file-read* (literal "/var/db/xcode_select_link"))',
        '(allow file-read* (literal "/private/var/db/xcode_select_link"))',
        '(allow file-read* (literal "/private/var/select/sh"))',
        '(allow file-read* (literal "/var/select/sh"))',
        '(allow file-read* (subpath "/bin"))',
        '(allow file-read* (subpath "/sbin"))',
        '(allow file-read* (subpath "/Library"))',
        '(allow file-read* (subpath "/private/etc"))',
        '(allow file-read* (subpath "/private/var/db/dyld"))',
        '(allow file-read* (subpath "/dev"))',
        "(allow process-fork)",
        "(allow sysctl-read)",
        '(allow mach-lookup (global-name "com.apple.logd"))',
        f'(allow file-read* (subpath "{repo}"))',
        f'(allow file-read-metadata file-test-existence (subpath "{repo_parent_ancestors}"))',
        f'(allow file-read-metadata file-test-existence (subpath "{repo_ancestors}"))',
        *(f'(allow file-read-metadata file-test-existence (subpath "{item}"))' for item in readable_ancestors),
        *(f'(allow file-read* (literal "{item}"))' for item in executables),
        *(f'(allow file-read* (literal "{item}"))' for item in readable),
        *(f'(allow file-read* (subpath "{item}"))' for item in git_runtime),
        f'(deny file-write* (subpath "{repo}"))',
        f'(allow file-read-metadata file-test-existence (subpath "{scratch_ancestors}"))',
        f'(allow file-read* (subpath "{scratch}"))',
        f'(allow file-write* (subpath "{scratch}"))',
        '(allow network-outbound (literal "/private/var/run/mDNSResponder"))',
        f'(allow network-outbound (remote tcp "localhost:{endpoint.rsplit(":", 1)[1]}"))',
        "",
    ])


def validate_review_profile(
    profile: str, *, repository: Path, home: Path, provider_endpoint_host: str,
    git_executable: Path | str = "/usr/bin/git",
    git_runtime_paths: tuple[Path | str, ...] = (),
    readable_files: tuple[Path | str, ...] = (),
    allowed_executables: tuple[Path | str, ...] = (),
) -> None:
    expected = review_profile(
        repository=repository, home=home, provider_endpoint_host=provider_endpoint_host,
        git_executable=git_executable,
        git_runtime_paths=git_runtime_paths,
        readable_files=readable_files,
        allowed_executables=allowed_executables,
    )
    if profile != expected:
        raise ValueError("sandbox profile is not the exact generated review policy")
