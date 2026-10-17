from collections.abc import Callable
from typing import Any


def retry[T](fn: Callable[[], T], attempts: int, transient: Callable[[Any], str | None], *,
             call: str | None = None, delay: Callable[[int], float] = lambda attempt: 3 ** attempt) -> T:
    from lokay.effects.pi import retry_sleep
    from lokay.store import log_event

    for attempt in range(attempts):
        try:
            result = fn()
        except Exception as exc:
            if attempt == attempts - 1:
                raise
            reason = transient(exc)
            if reason is None:
                raise
        else:
            if attempt == attempts - 1:
                return result
            reason = transient(result)
            if reason is None:
                return result
        if call is not None:
            log_event("retry", call=call, attempt=attempt + 1, reason=reason)
        retry_sleep(delay(attempt))
    raise AssertionError("unreachable")
