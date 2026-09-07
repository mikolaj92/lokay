"""Identity of loaded Python code, never a claim about transitive dependencies."""
from __future__ import annotations

import hashlib
import marshal
import sys
from typing import Callable, Any


def implementation_identity(handler: Callable[..., Any]) -> dict[str, Any]:
    """Snapshot a callable without reading possibly replaced checkout sources.

    Marshal is interpreter-version-specific; this digest is execution evidence,
    not a cross-language semantic fingerprint. Globals, imports and native code
    are deliberately not claimed as covered by the callable's code digest.
    """
    code = handler.__code__
    return {
        'symbol': f'{handler.__module__}:{handler.__qualname__}',
        'code_sha256': hashlib.sha256(marshal.dumps(code)).hexdigest(),
        'python_cache_tag': sys.implementation.cache_tag,
        'line': code.co_firstlineno,
        'scope': 'loaded_callable_only',
    }
