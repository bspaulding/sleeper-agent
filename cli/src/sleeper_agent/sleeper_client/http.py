"""Low-level HTTP GET helper shared by every sleeper_client resource module.

`get_json` is the one place that calls `requests` directly. Retry-with-backoff
on 429/5xx lives here since Sleeper's rate limit (1000 req/min) is generous
enough that this is a robustness measure, not real rate limiting. `sleep` is
an explicit injectable parameter purely so retry tests don't wait through
real delays — this is normal parameter-threading, not the banned
transport-mocking pattern, since `requests` itself is never replaced.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import requests

# Overridable for local wargaming against a mock Sleeper server (see
# scripts/wargame_server.py). Read at import time — one process, one base URL.
SLEEPER_BASE_URL = os.environ.get(
    "SLEEPER_AGENT_BASE_URL", "https://api.sleeper.app/v1"
)

_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 4
_BACKOFF_BASE_SECONDS = 1.0


class SleeperHTTPError(Exception):
    def __init__(self, url: str, status_code: int) -> None:
        self.url = url
        self.status_code = status_code
        super().__init__(f"GET {url} failed with status {status_code}")


def get_json(
    url: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
    max_attempts: int = _MAX_ATTEMPTS,
) -> Any:
    last_status = 0
    for attempt in range(max_attempts):
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.json()
        last_status = response.status_code
        if (
            response.status_code not in _RETRYABLE_STATUSES
            or attempt == max_attempts - 1
        ):
            raise SleeperHTTPError(url, response.status_code)
        sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
    raise SleeperHTTPError(
        url, last_status
    )  # pragma: no cover - unreachable, loop always returns or raises
