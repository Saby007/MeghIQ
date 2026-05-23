"""Forecast tools — get cost forecasts for subscriptions and resource groups.

Uses the Azure Cost Management Forecast API:
  POST /providers/Microsoft.CostManagement/forecast
  https://learn.microsoft.com/en-us/rest/api/cost-management/forecast/usage
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from auth import get_subscription_id, get_token
from response import error_response, success_response
from tools.validators import (
    sanitize_error_message,
    validate_resource_group,
    validate_subscription_id,
)

logger = logging.getLogger(__name__)

API_VERSION = "2023-11-01"
BASE_URL = "https://management.azure.com"


def _build_forecast_payload(
    timeframe: str = "Custom",
    granularity: str = "Daily",
    custom_from: str | None = None,
    custom_to: str | None = None,
    group_by: list[str] | None = None,
    include_actual: bool = True,
    include_fresh_partial: bool = False,
) -> dict[str, Any]:
    """Build the Forecast API request body."""
    dataset: dict[str, Any] = {
        "granularity": granularity,
        "aggregation": {
            "totalCost": {"name": "Cost", "function": "Sum"},
        },
    }

    if group_by:
        dataset["grouping"] = [
            {"type": "Dimension", "name": dim} for dim in group_by
        ]

    payload: dict[str, Any] = {
        "type": "ActualCost",
        "timeframe": timeframe,
        "dataset": dataset,
        "includeActualCost": include_actual,
        "includeFreshPartialCost": include_fresh_partial,
    }

    if timeframe == "Custom" and custom_from and custom_to:
        payload["timePeriod"] = {
            "from": custom_from,
            "to": custom_to,
        }

    return payload


def _parse_forecast_response(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse forecast response into row dicts."""
    props = raw.get("properties", raw)
    columns = [col["name"] for col in props.get("columns", [])]
    rows = props.get("rows", [])
    return [dict(zip(columns, row)) for row in rows]


async def get_cost_forecast(
    subscription_id: str | None = None,
    resource_group: str | None = None,
    granularity: str = "Daily",
    forecast_days: int = 30,
    group_by: str = "",
    include_actual: bool = True,
) -> str:
    """Get cost forecast for a subscription or resource group."""
    try:
        sub_id = subscription_id or get_subscription_id()
        sub_id = validate_subscription_id(sub_id)
        if resource_group:
            resource_group = validate_resource_group(resource_group)
            scope = f"subscriptions/{sub_id}/resourceGroups/{resource_group}"
        else:
            scope = f"subscriptions/{sub_id}"

        now = datetime.now(timezone.utc)
        custom_from = now.strftime("%Y-%m-%dT00:00:00Z")
        custom_to = (now + timedelta(days=forecast_days)).strftime("%Y-%m-%dT00:00:00Z")

        groups = [g.strip() for g in group_by.split(",") if g.strip()] if group_by else None

        payload = _build_forecast_payload(
            timeframe="Custom",
            granularity=granularity,
            custom_from=custom_from,
            custom_to=custom_to,
            group_by=groups,
            include_actual=include_actual,
        )

        url = f"{BASE_URL}/{scope}/providers/Microsoft.CostManagement/forecast?api-version={API_VERSION}"
        token = get_token()

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "60")
            return error_response(
                f"Rate limited by Azure API. Retry after {retry_after}s.",
                code="TooManyRequests",
            )

        if resp.status_code != 200:
            return error_response(
                sanitize_error_message(f"Azure Forecast API error {resp.status_code}: {resp.text}"),
                code=str(resp.status_code),
            )

        data = resp.json()
        parsed = _parse_forecast_response(data)
        return success_response(
            parsed,
            scope=scope,
            timeframe=f"{custom_from} to {custom_to}",
            currency="USD",
            extra_meta={"forecastDays": forecast_days, "granularity": granularity},
        )
    except Exception as e:
        logger.exception("get_cost_forecast failed")
        return error_response(sanitize_error_message(str(e)))
