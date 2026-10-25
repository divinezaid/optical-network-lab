"""Poll-until-true with a timeout: the core of asynchronous verification.

A device doesn't react instantly. Checking right after an action is flaky,
and a fixed sleep is either too slow or too short. So we poll until the
condition holds or the timeout expires, and we record how long it took.
"""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


class WaitTimeout(AssertionError):
    pass


def wait_for(
    condition: Callable[[], T],
    *,
    timeout_s: float,
    interval_s: float = 0.1,
    what: str = "condition",
) -> T:
    """Return the first truthy value of `condition()`, or fail after `timeout_s`."""
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while True:
        try:
            result = condition()
            if result:
                return result
        except Exception as exc:  # e.g. node still starting up
            last_error = exc
        if time.monotonic() >= deadline:
            detail = f" (last error: {last_error!r})" if last_error else ""
            raise WaitTimeout(f"timed out after {timeout_s}s waiting for {what}{detail}")
        time.sleep(interval_s)
