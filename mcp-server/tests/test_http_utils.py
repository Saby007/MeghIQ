"""Unit tests for ``tools.http_utils``.

These tests use ``httpx.MockTransport`` to fabricate Azure REST responses
so no Azure credentials or network access are required.
"""

from __future__ import annotations

import json
import os
import sys

import httpx
import pytest

# Make the package root importable so ``import tools.http_utils`` works
# regardless of the cwd the test runner is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.http_utils import (  # noqa: E402  (path setup above must come first)
    check_azure_response,
    handle_azure_error,
    handle_rate_limit,
)


def _make_response(
    status: int,
    body: str = "",
    headers: dict[str, str] | None = None,
    url: str = "https://management.azure.com/test",
) -> httpx.Response:
    """Build a real httpx.Response with an associated Request (for url)."""
    request = httpx.Request("GET", url)
    return httpx.Response(
        status_code=status,
        content=body.encode("utf-8"),
        headers=headers or {},
        request=request,
    )


# ── handle_rate_limit ────────────────────────────────────────────────


def test_handle_rate_limit_returns_none_for_200():
    resp = _make_response(200, '{"ok": true}')
    assert handle_rate_limit(resp) is None


def test_handle_rate_limit_returns_envelope_for_429():
    resp = _make_response(429, "throttled", headers={"Retry-After": "30"})
    out = handle_rate_limit(resp)
    assert out is not None
    parsed = json.loads(out)
    assert parsed["status"] == "error"
    assert parsed["error"]["code"] == "TooManyRequests"
    assert "30s" in parsed["error"]["message"]


def test_handle_rate_limit_defaults_retry_after_to_60s():
    resp = _make_response(429, "throttled")  # no Retry-After header
    out = handle_rate_limit(resp)
    assert out is not None
    parsed = json.loads(out)
    assert "60s" in parsed["error"]["message"]


# ── handle_azure_error ───────────────────────────────────────────────


def test_handle_azure_error_returns_none_for_2xx():
    for status in (200, 201, 204, 299):
        resp = _make_response(status, "ok")
        assert handle_azure_error(resp) is None, f"failed for status {status}"


def test_handle_azure_error_returns_envelope_for_4xx():
    resp = _make_response(404, '{"error":{"message":"not found"}}')
    out = handle_azure_error(resp, api_label="Cost Management")
    assert out is not None
    parsed = json.loads(out)
    assert parsed["status"] == "error"
    assert parsed["error"]["code"] == "404"
    assert "Cost Management" in parsed["error"]["message"]


def test_handle_azure_error_returns_envelope_for_5xx():
    resp = _make_response(503, "service unavailable")
    out = handle_azure_error(resp)
    assert out is not None
    parsed = json.loads(out)
    assert parsed["status"] == "error"
    assert parsed["error"]["code"] == "503"


def test_handle_azure_error_delegates_429_to_rate_limit():
    resp = _make_response(429, "throttled", headers={"Retry-After": "15"})
    out = handle_azure_error(resp)
    assert out is not None
    parsed = json.loads(out)
    assert parsed["error"]["code"] == "TooManyRequests"
    assert "15s" in parsed["error"]["message"]


def test_handle_azure_error_does_not_leak_upstream_body():
    """The raw response body must NOT appear in the client-visible envelope."""
    secret = "INTERNAL_AZURE_TRACE_ID=abc123-do-not-leak"
    resp = _make_response(500, secret)
    out = handle_azure_error(resp)
    assert out is not None
    assert secret not in out


# ── check_azure_response ─────────────────────────────────────────────


def test_check_azure_response_allows_default_200():
    resp = _make_response(200)
    assert check_azure_response(resp) is None


def test_check_azure_response_honours_allow_statuses():
    # 204 No Content: should be allowed when explicitly listed.
    resp = _make_response(204)
    assert check_azure_response(resp, allow_statuses=(200, 204)) is None
    # And rejected when not listed.
    resp2 = _make_response(204)
    out = check_azure_response(resp2, allow_statuses=(200,))
    assert out is not None
    assert json.loads(out)["status"] == "error"


def test_check_azure_response_routes_429_to_rate_limit():
    resp = _make_response(429, headers={"Retry-After": "45"})
    out = check_azure_response(resp)
    assert out is not None
    parsed = json.loads(out)
    assert parsed["error"]["code"] == "TooManyRequests"


def test_check_azure_response_routes_other_errors_to_generic_handler():
    resp = _make_response(400, "bad request")
    out = check_azure_response(resp, api_label="Resource Graph")
    assert out is not None
    parsed = json.loads(out)
    assert parsed["error"]["code"] == "400"
    assert "Resource Graph" in parsed["error"]["message"]


def test_check_azure_response_logs_retry_after(caplog):
    """Rate-limit handler emits a WARNING with retry_after + url for ops."""
    import logging

    caplog.set_level(logging.WARNING, logger="tools.http_utils")
    resp = _make_response(429, headers={"Retry-After": "7"})
    check_azure_response(resp)
    assert any(
        "retry_after=7" in record.getMessage() for record in caplog.records
    ), f"expected retry_after=7 in logs, got {[r.getMessage() for r in caplog.records]}"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
