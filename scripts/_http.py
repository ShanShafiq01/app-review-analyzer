"""
Shared HTTP utilities — resilient request handling with exponential backoff,
jitter, and rate-limit detection.

Designed for scraping public review feeds politely. The defaults err on the
side of patience over speed.
"""
from __future__ import annotations

import random
import sys
import time
from dataclasses import dataclass, field
from typing import Callable

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)


# Backoff schedule with jitter — 5s, 15s, 45s with ±20% randomization
BACKOFF_SCHEDULE = [5, 15, 45]
JITTER_PCT = 0.2

# HTTP status codes that mean "back off and retry"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Status codes that mean "this resource doesn't exist" — no retry
PERMANENT_FAILURE = {400, 401, 403, 404, 410}

DEFAULT_TIMEOUT = 15


@dataclass
class FetchSession:
    """
    A request session with retry logic, jitter, and progress callbacks.

    Tracks consecutive failures across requests so the caller can detect
    when a host is fully blocking and gracefully degrade.
    """
    user_agent: str = "Mozilla/5.0 (compatible; AppReviewAnalyzer/0.2; +https://github.com)"
    timeout: int = DEFAULT_TIMEOUT
    progress_callback: Callable[[str], None] | None = None

    consecutive_failures: int = field(default=0, init=False)
    total_requests: int = field(default=0, init=False)
    total_retries: int = field(default=0, init=False)
    session: requests.Session = field(default=None, init=False)

    def __post_init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent, "Accept": "application/json"})

    def _log(self, msg: str):
        """Send a user-friendly progress message."""
        if self.progress_callback:
            self.progress_callback(msg)
        else:
            print(msg, file=sys.stderr)

    def _jittered_sleep(self, base_seconds: int):
        """Sleep for base_seconds ± JITTER_PCT, with progress message."""
        jitter = base_seconds * JITTER_PCT
        actual = base_seconds + random.uniform(-jitter, jitter)
        actual = max(1.0, actual)
        # Show countdown for long waits
        if actual >= 10:
            self._log(f"  Waiting {actual:.0f}s before retry...")
        time.sleep(actual)

    def fetch_json(self, url: str, *, retries: int = 3) -> dict | None:
        """
        Fetch a URL and parse as JSON.

        Returns:
            Parsed JSON dict on success.
            None on permanent failure (4xx that aren't 429).
            Raises RateLimitedError if retries are exhausted on retryable errors.
        """
        self.total_requests += 1
        last_status = None

        for attempt in range(retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                last_status = resp.status_code

                if resp.status_code == 200:
                    # Success — reset failure counter
                    self.consecutive_failures = 0
                    try:
                        return resp.json()
                    except ValueError:
                        # Got 200 but invalid JSON — treat as permanent
                        return None

                if resp.status_code in PERMANENT_FAILURE:
                    # No retry for these
                    self.consecutive_failures += 1
                    return None

                if resp.status_code in RETRYABLE_STATUS:
                    if attempt < retries:
                        wait = BACKOFF_SCHEDULE[min(attempt, len(BACKOFF_SCHEDULE) - 1)]
                        # Honor Retry-After header if Apple sends one
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after:
                            try:
                                wait = max(wait, int(retry_after))
                            except ValueError:
                                pass
                        self._log(f"  Rate-limited (HTTP {resp.status_code}). Backing off {wait}s — this is normal for popular apps")
                        self.total_retries += 1
                        self._jittered_sleep(wait)
                        continue
                    else:
                        # Exhausted retries
                        self.consecutive_failures += 1
                        raise RateLimitedError(
                            f"Rate-limited after {retries} retries (last status: {resp.status_code})",
                            url=url,
                            status=resp.status_code,
                        )

                # Other status code we don't know about — treat as failure
                self.consecutive_failures += 1
                return None

            except requests.Timeout:
                if attempt < retries:
                    wait = BACKOFF_SCHEDULE[min(attempt, len(BACKOFF_SCHEDULE) - 1)]
                    self._log(f"  Request timed out, retrying in {wait}s...")
                    self.total_retries += 1
                    self._jittered_sleep(wait)
                    continue
                self.consecutive_failures += 1
                raise RateLimitedError(f"Timeout after {retries} retries", url=url)

            except requests.ConnectionError as exc:
                if attempt < retries:
                    wait = BACKOFF_SCHEDULE[min(attempt, len(BACKOFF_SCHEDULE) - 1)]
                    self._log(f"  Connection error, retrying in {wait}s...")
                    self.total_retries += 1
                    self._jittered_sleep(wait)
                    continue
                self.consecutive_failures += 1
                raise RateLimitedError(f"Connection failed after {retries} retries", url=url)

        return None

    def should_give_up(self, threshold: int = 3) -> bool:
        """
        Has the host given us so many failures that we should stop trying?
        Default: 3 consecutive failures = host is meaningfully blocking us.
        """
        return self.consecutive_failures >= threshold

    def polite_pause(self, seconds: float = 0.3):
        """Brief pause between successful requests — be a good citizen."""
        time.sleep(seconds + random.uniform(0, 0.1))


class RateLimitedError(Exception):
    """Raised when retries are exhausted on a retryable error."""
    def __init__(self, message: str, url: str = None, status: int = None):
        super().__init__(message)
        self.url = url
        self.status = status
