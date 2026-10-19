"""Safe diagnostics: never serialize exceptions, request bodies or credentials."""
from __future__ import annotations

import logging
import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import ValidationError


def failure_category(error: BaseException) -> str:
    if isinstance(error, (TimeoutError, httpx.TimeoutException, APITimeoutError)):
        return 'timeout'
    if isinstance(error, (httpx.NetworkError, APIConnectionError)):
        return 'connection'
    if isinstance(error, (httpx.HTTPStatusError, APIStatusError)):
        status = error.response.status_code
        return {401: 'authentication', 403: 'permission', 409: 'conflict',
                422: 'validation', 429: 'rate_limit'}.get(status, 'http_error')
    if isinstance(error, (ValidationError, ValueError)):
        return 'validation'
    return 'unexpected'


def log_failure(stage: str, error: BaseException, interview_id: str,
                turn_id: str = '-', failures: int = 1) -> None:
    code = '-'
    if isinstance(error, httpx.HTTPStatusError):
        try:
            body = error.response.json()
            candidate = body.get('error', {}).get('code')
            if candidate in ('INVALID_EVIDENCE', 'INVALID_ANSWER', 'INTERVIEW_CLOSED',
                             'IDEMPOTENCY_CONFLICT', 'TURN_LIMIT'):
                code = candidate
        except (ValueError, AttributeError, TypeError):
            pass
    # Only internally supplied identifiers and categories; no exception message/traceback.
    logging.getLogger('founder').warning(
        'Voice operation failed stage=%s category=%s code=%s interview=%s turn=%s failures=%s',
        stage, failure_category(error), code, interview_id, turn_id, failures)


def transient_backend_error(error: httpx.HTTPError) -> bool:
    return not isinstance(error, httpx.HTTPStatusError) or error.response.status_code in (
        408, 429, 500, 502, 503, 504)
