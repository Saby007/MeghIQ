"""Lightweight in-process telemetry for the MeghIQ MCP server.

Provides three concerns without any external dependency:

  * **Request IDs** — every tool invocation gets a short opaque id stored
    in a ``contextvars.ContextVar`` so log records emitted anywhere down
    the call stack can be correlated to a single tool call.

  * **Latency & counters** — per-tool call/error counts and a running
    average latency. Snapshot is exposed via :func:`telemetry_snapshot`
    and surfaced by the ``/metrics`` Starlette route.

  * **Instrumentation decorator** — :func:`instrument` wraps an async
    tool with id allocation, latency timing, error detection (by parsing
    the structured JSON envelope returned by ``response.error_response``),
    counter recording, and a single structured log line per invocation.

The module deliberately avoids any wire-format dependency (no OTLP,
Prometheus client, etc.) — counters are exposed as JSON over the
existing health endpoint surface.
"""

from __future__ import annotations

import inspect
import json
import logging
import time
import typing
import uuid
from collections import defaultdict
from contextvars import ContextVar
from functools import wraps
from threading import Lock
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

# ── Request-id context ───────────────────────────────────────────────

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Return the request id bound to the current async context, if any."""
    return _request_id_var.get()


class RequestContextFilter(logging.Filter):
    """Logging filter that injects ``%(request_id)s`` into every record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        record.request_id = _request_id_var.get() or "-"
        return True


# ── Counters ─────────────────────────────────────────────────────────


class _Counters:
    """Thread-safe in-memory counters keyed by tool name."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._calls: dict[str, int] = defaultdict(int)
        self._errors: dict[str, int] = defaultdict(int)
        self._latency_ms_sum: dict[str, float] = defaultdict(float)
        self._latency_ms_max: dict[str, float] = defaultdict(float)

    def record(self, tool: str, latency_ms: float, error: bool) -> None:
        with self._lock:
            self._calls[tool] += 1
            self._latency_ms_sum[tool] += latency_ms
            if latency_ms > self._latency_ms_max[tool]:
                self._latency_ms_max[tool] = latency_ms
            if error:
                self._errors[tool] += 1

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                tool: {
                    "calls": self._calls[tool],
                    "errors": self._errors[tool],
                    "avg_latency_ms": round(
                        self._latency_ms_sum[tool] / self._calls[tool], 2
                    )
                    if self._calls[tool]
                    else 0.0,
                    "max_latency_ms": round(self._latency_ms_max[tool], 2),
                }
                for tool in self._calls
            }

    def totals(self) -> dict[str, int]:
        with self._lock:
            return {
                "tool_calls_total": sum(self._calls.values()),
                "tool_errors_total": sum(self._errors.values()),
                "unique_tools": len(self._calls),
            }


_counters = _Counters()


def telemetry_snapshot() -> dict[str, Any]:
    """Return a JSON-serialisable snapshot of all in-memory counters."""
    return {
        "totals": _counters.totals(),
        "tools": _counters.snapshot(),
    }


# ── Instrumentation decorator ───────────────────────────────────────

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def _result_indicates_error(result: Any) -> bool:
    """Best-effort: did the tool return a ``{"status": "error", ...}`` JSON?"""
    if not isinstance(result, str):
        return False
    # Quick string sniff before parsing to avoid JSON cost on success paths.
    if '"status"' not in result or '"error"' not in result:
        return False
    try:
        parsed = json.loads(result)
    except (ValueError, TypeError):
        return False
    return isinstance(parsed, dict) and parsed.get("status") == "error"


def instrument(tool_name: str | None = None) -> Callable[[F], F]:
    """Decorator that wraps an async MCP tool with telemetry.

    On every invocation:
      * a short request-id is generated and bound to the current context;
      * the wall-clock latency is measured;
      * the result is inspected to detect a structured error response;
      * a single ``INFO``-level log line is emitted summarising the call;
      * per-tool counters are updated atomically.

    The decorator is signature-preserving and does not modify args or the
    return value.
    """

    def deco(fn: F) -> F:
        name = tool_name or getattr(fn, "__name__", "anonymous_tool")

        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            rid = uuid.uuid4().hex[:12]
            token = _request_id_var.set(rid)
            t0 = time.perf_counter()
            error = False
            try:
                result = await fn(*args, **kwargs)
                if _result_indicates_error(result):
                    error = True
                return result
            except Exception:
                error = True
                raise
            finally:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                _counters.record(name, latency_ms, error)
                logger.info(
                    "mcp_tool_call tool=%s status=%s latency_ms=%.1f request_id=%s",
                    name,
                    "error" if error else "ok",
                    latency_ms,
                    rid,
                )
                _request_id_var.reset(token)

        # Pre-resolve annotations on the wrapper. FastMCP's signature
        # introspection follows ``__wrapped__`` for parameters but reads
        # ``__globals__`` from the wrapper (which lives in *this* module
        # and therefore cannot resolve ForwardRefs like ``SubscriptionId``
        # defined in the caller's module). Setting ``__signature__`` with
        # already-evaluated annotations bypasses that lookup entirely.
        try:
            sig = inspect.signature(fn)
            hints = typing.get_type_hints(fn, include_extras=True)
            new_params = [
                p.replace(annotation=hints.get(p.name, p.annotation))
                for p in sig.parameters.values()
            ]
            return_anno = hints.get("return", sig.return_annotation)
            wrapper.__signature__ = sig.replace(  # type: ignore[attr-defined]
                parameters=new_params, return_annotation=return_anno
            )
            wrapper.__annotations__ = hints
        except Exception:  # pragma: no cover - introspection best-effort
            logger.debug("instrument: could not pre-resolve annotations for %s", name)

        return wrapper  # type: ignore[return-value]

    return deco


__all__ = [
    "RequestContextFilter",
    "get_request_id",
    "instrument",
    "telemetry_snapshot",
]
