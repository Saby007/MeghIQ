"""Unit tests for ``telemetry`` (request IDs, counters, instrument decorator)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Annotated

import pytest
from pydantic import Field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telemetry import (  # noqa: E402
    RequestContextFilter,
    _result_indicates_error,
    get_request_id,
    instrument,
    telemetry_snapshot,
)

# Module-level alias so ``typing.get_type_hints`` can resolve the
# ForwardRef inside ``test_instrument_preserves_signature_for_introspection``.
# This mirrors how server.py defines its shared parameter aliases.
TestAlias = Annotated[str, Field(default="", description="x", max_length=5)]


# ── _result_indicates_error ──────────────────────────────────────────


def test_result_indicates_error_detects_envelope():
    err = json.dumps({"status": "error", "error": {"message": "boom"}})
    assert _result_indicates_error(err) is True


def test_result_indicates_error_ignores_success_envelope():
    ok = json.dumps({"status": "success", "data": []})
    assert _result_indicates_error(ok) is False


def test_result_indicates_error_ignores_non_string():
    assert _result_indicates_error({"status": "error"}) is False
    assert _result_indicates_error(None) is False
    assert _result_indicates_error(42) is False


def test_result_indicates_error_handles_plain_strings():
    assert _result_indicates_error("just a string") is False


def test_result_indicates_error_ignores_invalid_json():
    # Contains both substrings but is not valid JSON — must not raise.
    assert _result_indicates_error('"status": "error" garbage') is False


# ── RequestContextFilter ─────────────────────────────────────────────


def test_request_context_filter_injects_dash_when_unset():
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", (), None)
    assert RequestContextFilter().filter(rec) is True
    assert rec.request_id == "-"


# ── instrument decorator (success path) ──────────────────────────────


def test_instrument_records_successful_call():
    @instrument("t_success_unique")
    async def ok() -> str:
        return json.dumps({"status": "success", "data": []})

    asyncio.run(ok())
    snap = telemetry_snapshot()
    assert snap["tools"]["t_success_unique"]["calls"] >= 1
    assert snap["tools"]["t_success_unique"]["errors"] == 0


def test_instrument_detects_error_envelope():
    @instrument("t_err_envelope_unique")
    async def err() -> str:
        return json.dumps({"status": "error", "error": {"message": "x"}})

    asyncio.run(err())
    snap = telemetry_snapshot()
    assert snap["tools"]["t_err_envelope_unique"]["errors"] >= 1


def test_instrument_counts_exception_as_error_and_reraises():
    @instrument("t_exc_unique")
    async def boom() -> str:
        raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError):
        asyncio.run(boom())

    snap = telemetry_snapshot()
    assert snap["tools"]["t_exc_unique"]["calls"] >= 1
    assert snap["tools"]["t_exc_unique"]["errors"] >= 1


# ── request-id context ──────────────────────────────────────────────


def test_instrument_binds_request_id_inside_call_and_clears_after():
    captured: dict[str, str | None] = {}

    @instrument("t_rid_unique")
    async def grab() -> str:
        captured["inside"] = get_request_id()
        return json.dumps({"status": "success", "data": []})

    asyncio.run(grab())
    assert captured["inside"] is not None
    assert len(captured["inside"]) == 12  # uuid4().hex[:12]
    # After the call, the contextvar must be reset (no leakage).
    assert get_request_id() is None


# ── snapshot shape ───────────────────────────────────────────────────


def test_telemetry_snapshot_shape():
    @instrument("t_shape_unique")
    async def t() -> str:
        return json.dumps({"status": "success"})

    asyncio.run(t())
    snap = telemetry_snapshot()
    assert "totals" in snap and "tools" in snap
    totals = snap["totals"]
    assert {"tool_calls_total", "tool_errors_total", "unique_tools"} <= totals.keys()
    tool = snap["tools"]["t_shape_unique"]
    assert {"calls", "errors", "avg_latency_ms", "max_latency_ms"} <= tool.keys()


# ── signature pre-resolution (important for FastMCP integration) ────


def test_instrument_preserves_signature_for_introspection():
    """FastMCP relies on ``inspect.signature(wrapper)`` returning the original
    parameter annotations. The decorator must pre-resolve them onto the
    wrapper so FastMCP doesn't try to evaluate ForwardRefs against the
    telemetry module's globals.
    """
    import inspect

    @instrument("t_sig_unique")
    async def f(a: TestAlias = "") -> str:  # noqa: ARG001
        return "ok"

    sig = inspect.signature(f)
    param = sig.parameters["a"]
    # After pre-resolution, the annotation must NOT be a bare string or
    # ForwardRef — it should be the resolved Annotated type.
    assert not isinstance(param.annotation, str)
    # Metadata is preserved on Annotated types via __metadata__.
    assert hasattr(param.annotation, "__metadata__")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
