"""Standardised JSON response helpers for all MCP tools.

Every tool returns a dict with:
  - status: "success" | "error"
  - data: the actual payload (list, dict, etc.)
  - metadata: scope, timeframe, currency, rowCount, etc.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def success_response(
    data: Any,
    *,
    scope: str | None = None,
    timeframe: str | None = None,
    currency: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> str:
    """Build a standardised success JSON string."""
    metadata: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if scope:
        metadata["scope"] = scope
    if timeframe:
        metadata["timeframe"] = timeframe
    if currency:
        metadata["currency"] = currency
    if isinstance(data, list):
        metadata["rowCount"] = len(data)

    if extra_meta:
        metadata.update(extra_meta)

    return json.dumps(
        {"status": "success", "data": data, "metadata": metadata},
        indent=2,
        default=str,
    )


def error_response(message: str, *, code: str | None = None) -> str:
    """Build a standardised error JSON string."""
    payload: dict[str, Any] = {
        "status": "error",
        "error": {"message": message},
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()},
    }
    if code:
        payload["error"]["code"] = code
    return json.dumps(payload, indent=2, default=str)
