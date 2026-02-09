"""
Retry Decorator with Exponential Backoff
Aviation Intelligence Platform - Pipeline Monitoring (Epic 1.8)

Provides configurable retry logic for external API calls using tenacity.
Pattern matches existing gemini_service.py implementation.
"""

import logging
from functools import wraps
from typing import Tuple, Type, Callable, Any
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError
)

logger = logging.getLogger(__name__)


# ============================================================================
# RETRYABLE EXCEPTIONS
# ============================================================================

# Transient failures that should be retried
RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
    ConnectionResetError,
    TimeoutError,
)

# Non-retryable HTTP status codes (client errors that won't succeed on retry)
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}


# ============================================================================
# CUSTOM RETRY PREDICATES
# ============================================================================

def is_retryable_http_error(exception: Exception) -> bool:
    """
    Determine if an HTTP error should be retried.

    Retries on:
    - 429 Too Many Requests
    - 500, 502, 503, 504 Server Errors

    Does NOT retry on:
    - 400 Bad Request
    - 401 Unauthorized
    - 403 Forbidden
    - 404 Not Found
    - 422 Unprocessable Entity
    """
    if isinstance(exception, requests.exceptions.HTTPError):
        if hasattr(exception, 'response') and exception.response is not None:
            status_code = exception.response.status_code
            if status_code in NON_RETRYABLE_STATUS_CODES:
                return False
            # Retry on server errors and rate limits
            return status_code >= 429
    return False


def should_retry(exception: Exception) -> bool:
    """Combined retry predicate for all retryable conditions."""
    # Check if it's a retryable exception type
    if isinstance(exception, RETRYABLE_EXCEPTIONS):
        return True
    # Check if it's a retryable HTTP error
    if is_retryable_http_error(exception):
        return True
    return False


# ============================================================================
# RETRY DECORATOR FACTORY
# ============================================================================

def with_retry(
    max_attempts: int = 3,
    min_wait: float = 2.0,
    max_wait: float = 30.0,
    exceptions: Tuple[Type[Exception], ...] = None
) -> Callable:
    """
    Create a configurable retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        min_wait: Minimum wait time in seconds (default: 2)
        max_wait: Maximum wait time in seconds (default: 30)
        exceptions: Tuple of exception types to retry on (default: RETRYABLE_EXCEPTIONS)

    Returns:
        Configured retry decorator

    Example:
        @with_retry(max_attempts=5, min_wait=1, max_wait=60)
        def fetch_data():
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
    """
    retry_exceptions = exceptions or RETRYABLE_EXCEPTIONS

    def decorator(func: Callable) -> Callable:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(retry_exceptions),
            reraise=True,
            before_sleep=before_sleep_log(logger, logging.WARNING)
        )
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================================
# PRE-CONFIGURED DECORATORS
# ============================================================================

# Standard API call retry (3 attempts, 2-30s backoff)
retry_api_call = with_retry(max_attempts=3, min_wait=2, max_wait=30)

# Web scraping retry (2 attempts, 1-10s backoff) - faster timeout for scraping
retry_scrape = with_retry(max_attempts=2, min_wait=1, max_wait=10)

# Heavy API calls (5 attempts, 5-60s backoff) - for slow APIs like SEC EDGAR
retry_heavy = with_retry(max_attempts=5, min_wait=5, max_wait=60)

# Light retry (2 attempts, 1-5s) - for quick fallback scenarios
retry_light = with_retry(max_attempts=2, min_wait=1, max_wait=5)


# ============================================================================
# RETRY WRAPPER FOR HTTP RESPONSES
# ============================================================================

def retry_on_server_error(func: Callable) -> Callable:
    """
    Decorator that retries on 5xx server errors.
    Raises the response for non-2xx status codes after retries.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> requests.Response:
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type((requests.exceptions.HTTPError,)),
            reraise=True,
            before_sleep=before_sleep_log(logger, logging.WARNING)
        )
        def inner() -> requests.Response:
            response = func(*args, **kwargs)
            # Raise for server errors to trigger retry
            if response.status_code >= 500:
                response.raise_for_status()
            return response

        try:
            return inner()
        except RetryError:
            # Return the last response if all retries failed
            return func(*args, **kwargs)

    return wrapper


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def make_request_with_retry(
    url: str,
    method: str = 'GET',
    timeout: int = 30,
    max_retries: int = 3,
    **kwargs: Any
) -> requests.Response:
    """
    Make an HTTP request with automatic retry on transient failures.

    Args:
        url: URL to request
        method: HTTP method (GET, POST, etc.)
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        **kwargs: Additional arguments passed to requests

    Returns:
        Response object

    Raises:
        requests.exceptions.RequestException: If all retries fail
    """
    @with_retry(max_attempts=max_retries)
    def _make_request() -> requests.Response:
        response = requests.request(method, url, timeout=timeout, **kwargs)
        # Raise for server errors to trigger retry
        if response.status_code >= 500 or response.status_code == 429:
            response.raise_for_status()
        return response

    return _make_request()
