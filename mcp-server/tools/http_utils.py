"""Shared HTTP-response helpers for tools that call Azure REST APIs.

Centralises rate-limit (HTTP 429) handling and error-response sanitization
so every tool reports failures consistently and never leaks raw upstream
response bodies to MCP clients.
"""

from __future__ import annotations

import logging

import httpx

from response import error_response
from tools.validators import sanitize_error_message

logger = logging.getLogger(__name__)


def handle_rate_limit(resp: httpx.Response) -> str | None:
    """If the response is HTTP 429, return a sanitised error_response JSON.

    Honours the ``Retry-After`` response header (defaults to 60s when absent).
    Returns ``None`` when the response is not a rate-limit response.
    """
    if resp.status_code != 429:
        return None
    retry_after = resp.headers.get("Retry-After", "60")
    logger.warning(
        "Azure API rate-limited (status=429, retry_after=%s, url=%s)",
        retry_after,
        resp.request.url if resp.request else "<unknown>",
    )
    return error_response(
        f"Rate limited by Azure API. Retry after {retry_after}s.",
        code="TooManyRequests",
    )


def handle_azure_error(
    resp: httpx.Response,
    api_label: str = "Azure API",
) -> str | None:
    """If the response is a non-2xx error, return a sanitised error_response JSON.

    Logs the raw upstream body server-side (for debugging) but only the
    sanitised status code is included in the client-visible error.

    Returns ``None`` when the response is successful (2xx).
    """
    if 200 <= resp.status_code < 300:
        return None

    # Rate-limit responses get a more specific message via handle_rate_limit;
    # callers should invoke that first, but handle here too as a safety net.
    if resp.status_code == 429:
        return handle_rate_limit(resp)

    # Log the raw body server-side only, never returned to the client.
    try:
        logger.warning(
            "%s error (status=%d, url=%s): %s",
            api_label,
            resp.status_code,
            resp.request.url if resp.request else "<unknown>",
            resp.text[:500],
        )
    except Exception:  # noqa: BLE001 — best-effort logging
        pass

    return error_response(
        sanitize_error_message(f"{api_label} error {resp.status_code}"),
        code=str(resp.status_code),
    )


def check_azure_response(
    resp: httpx.Response,
    api_label: str = "Azure API",
    allow_statuses: tuple[int, ...] = (200,),
) -> str | None:
    """One-shot helper that returns a sanitised error if status not allowed.

    Combines rate-limit handling and generic error reporting. Pass the set
    of acceptable status codes via ``allow_statuses`` (default: ``(200,)``).

    A 2xx response whose status is *not* in ``allow_statuses`` is also
    reported as an error — callers that have opted into a specific success
    set should not silently accept e.g. ``204 No Content`` when they asked
    for ``200`` only.
    """
    if resp.status_code in allow_statuses:
        return None
    rl = handle_rate_limit(resp)
    if rl is not None:
        return rl
    if 200 <= resp.status_code < 300:
        try:
            logger.warning(
                "%s unexpected success status (status=%d, allowed=%s, url=%s)",
                api_label,
                resp.status_code,
                allow_statuses,
                resp.request.url if resp.request else "<unknown>",
            )
        except Exception:  # noqa: BLE001 — best-effort logging
            pass
        return error_response(
            f"{api_label} returned unexpected status {resp.status_code}",
            code=str(resp.status_code),
        )
    return handle_azure_error(resp, api_label=api_label)


__all__: list[str] = [
    "check_azure_response",
    "handle_azure_error",
    "handle_rate_limit",
]
