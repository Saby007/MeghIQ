"""Cost query tools — query Azure costs by subscription, resource group, or management group.

Uses the Azure Cost Management Query API:
  POST /providers/Microsoft.CostManagement/query
  https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from auth import get_subscription_id, get_token
from response import error_response, success_response
from tools.validators import (
    sanitize_error_message,
    validate_management_group_id,
    validate_resource_group,
    validate_subscription_id,
)

logger = logging.getLogger(__name__)

API_VERSION = "2023-11-01"
BASE_URL = "https://management.azure.com"


def _build_query_payload(
    query_type: str = "ActualCost",
    timeframe: str = "MonthToDate",
    granularity: str = "Daily",
    group_by: list[str] | None = None,
    filter_expr: dict | None = None,
    custom_from: str | None = None,
    custom_to: str | None = None,
) -> dict[str, Any]:
    """Build the Cost Management Query API request body."""
    dataset: dict[str, Any] = {
        "granularity": granularity,
        "aggregation": {
            "totalCost": {"name": "Cost", "function": "Sum"},
            "totalCostUSD": {"name": "CostUSD", "function": "Sum"},
        },
    }

    if group_by:
        dataset["grouping"] = [
            {"type": "Dimension", "name": dim} for dim in group_by
        ]

    if filter_expr:
        dataset["filter"] = filter_expr

    payload: dict[str, Any] = {
        "type": query_type,
        "timeframe": timeframe,
        "dataset": dataset,
    }

    if timeframe == "Custom" and custom_from and custom_to:
        payload["timePeriod"] = {
            "from": custom_from,
            "to": custom_to,
        }

    return payload


def _parse_query_response(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse the Cost Management query response into a list of row dicts."""
    props = raw.get("properties", raw)
    columns = [col["name"] for col in props.get("columns", [])]
    rows = props.get("rows", [])

    return [dict(zip(columns, row)) for row in rows]


async def _execute_query(scope: str, payload: dict[str, Any]) -> str:
    """Execute a cost query against the given scope and return JSON."""
    url = f"{BASE_URL}/{scope}/providers/Microsoft.CostManagement/query?api-version={API_VERSION}"
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
                sanitize_error_message(f"Azure API error {resp.status_code}"),
                code=str(resp.status_code),
            )

        data = resp.json()
        parsed = _parse_query_response(data)
        return success_response(
            parsed,
            scope=scope,
            timeframe=payload.get("timeframe", ""),
            currency="USD",
        )


async def query_subscription_costs(
    subscription_id: str | None = None,
    query_type: str = "ActualCost",
    timeframe: str = "MonthToDate",
    granularity: str = "Daily",
    group_by: str = "ServiceName",
    custom_from: str | None = None,
    custom_to: str | None = None,
) -> str:
    """Query costs for an Azure subscription.

    Args:
        subscription_id: Azure subscription ID (defaults to AZURE_SUBSCRIPTION_ID env var).
        query_type: 'ActualCost' or 'AmortizedCost'.
        timeframe: MonthToDate, BillingMonthToDate, TheLastMonth, TheLastBillingMonth,
                   WeekToDate, or Custom.
        granularity: Daily, Monthly, or None (no time breakdown).
        group_by: Comma-separated dimension names to group by.
        custom_from: Start date (YYYY-MM-DD) when timeframe is Custom.
        custom_to: End date (YYYY-MM-DD) when timeframe is Custom.

    Returns:
        JSON with cost data rows grouped by the specified dimensions.
    """
    try:
        sub_id = (
            validate_subscription_id(subscription_id)
            if subscription_id
            else get_subscription_id()
        )
        scope = f"subscriptions/{sub_id}"
        groups = [g.strip() for g in group_by.split(",") if g.strip()]
        payload = _build_query_payload(
            query_type=query_type,
            timeframe=timeframe,
            granularity=granularity,
            group_by=groups,
            custom_from=custom_from,
            custom_to=custom_to,
        )
        return await _execute_query(scope, payload)
    except ValueError as ve:
        return error_response(sanitize_error_message(str(ve)), code="400")
    except Exception as e:
        logger.exception("query_subscription_costs failed")
        return error_response(sanitize_error_message(str(e)))


async def query_resource_group_costs(
    resource_group: str,
    subscription_id: str | None = None,
    query_type: str = "ActualCost",
    timeframe: str = "MonthToDate",
    granularity: str = "Daily",
    group_by: str = "ServiceName",
    custom_from: str | None = None,
    custom_to: str | None = None,
) -> str:
    """Query costs for a specific Azure resource group.

    Args:
        resource_group: Name of the resource group.
        subscription_id: Azure subscription ID (defaults to AZURE_SUBSCRIPTION_ID env var).
        query_type: 'ActualCost' or 'AmortizedCost'.
        timeframe: MonthToDate, BillingMonthToDate, TheLastMonth, TheLastBillingMonth,
                   WeekToDate, or Custom.
        granularity: Daily, Monthly, or None.
        group_by: Comma-separated dimensions to group by.
        custom_from: Start date (YYYY-MM-DD) when timeframe is Custom.
        custom_to: End date (YYYY-MM-DD) when timeframe is Custom.

    Returns:
        JSON with cost data rows for the resource group.
    """
    try:
        sub_id = (
            validate_subscription_id(subscription_id)
            if subscription_id
            else get_subscription_id()
        )
        rg = validate_resource_group(resource_group)
        scope = f"subscriptions/{sub_id}/resourceGroups/{rg}"
        groups = [g.strip() for g in group_by.split(",") if g.strip()]
        payload = _build_query_payload(
            query_type=query_type,
            timeframe=timeframe,
            granularity=granularity,
            group_by=groups,
            custom_from=custom_from,
            custom_to=custom_to,
        )
        return await _execute_query(scope, payload)
    except ValueError as ve:
        return error_response(sanitize_error_message(str(ve)), code="400")
    except Exception as e:
        logger.exception("query_resource_group_costs failed")
        return error_response(sanitize_error_message(str(e)))


async def query_management_group_costs(
    management_group_id: str,
    query_type: str = "ActualCost",
    timeframe: str = "MonthToDate",
    granularity: str = "Daily",
    group_by: str = "ServiceName",
    custom_from: str | None = None,
    custom_to: str | None = None,
) -> str:
    """Query costs for an Azure management group.

    Args:
        management_group_id: The management group ID.
        query_type: 'ActualCost' or 'AmortizedCost'.
        timeframe: MonthToDate, BillingMonthToDate, TheLastMonth, TheLastBillingMonth,
                   WeekToDate, or Custom.
        granularity: Daily, Monthly, or None.
        group_by: Comma-separated dimensions to group by.
        custom_from: Start date (YYYY-MM-DD) when timeframe is Custom.
        custom_to: End date (YYYY-MM-DD) when timeframe is Custom.

    Returns:
        JSON with cost data rows for the management group.
    """
    try:
        mg_id = validate_management_group_id(management_group_id)
        scope = f"providers/Microsoft.Management/managementGroups/{mg_id}"
        groups = [g.strip() for g in group_by.split(",") if g.strip()]
        payload = _build_query_payload(
            query_type=query_type,
            timeframe=timeframe,
            granularity=granularity,
            group_by=groups,
            custom_from=custom_from,
            custom_to=custom_to,
        )
        return await _execute_query(scope, payload)
    except ValueError as ve:
        return error_response(sanitize_error_message(str(ve)), code="400")
    except Exception as e:
        logger.exception("query_management_group_costs failed")
        return error_response(sanitize_error_message(str(e)))


async def compare_costs(
    period1_from: str,
    period1_to: str,
    period2_from: str,
    period2_to: str,
    subscription_id: str | None = None,
    group_by: str = "ServiceName",
    granularity: str = "None",
) -> str:
    """Compare costs between two custom time periods.

    Args:
        period1_from: Start date for period 1 (YYYY-MM-DD).
        period1_to: End date for period 1 (YYYY-MM-DD).
        period2_from: Start date for period 2 (YYYY-MM-DD).
        period2_to: End date for period 2 (YYYY-MM-DD).
        subscription_id: Azure subscription ID (defaults to AZURE_SUBSCRIPTION_ID env var).
        group_by: Comma-separated dimensions to group by.
        granularity: Daily, Monthly, or None.

    Returns:
        JSON with cost data for both periods for comparison.
    """
    try:
        sub_id = (
            validate_subscription_id(subscription_id)
            if subscription_id
            else get_subscription_id()
        )
        scope = f"subscriptions/{sub_id}"
        groups = [g.strip() for g in group_by.split(",") if g.strip()]

        payload1 = _build_query_payload(
            timeframe="Custom",
            granularity=granularity,
            group_by=groups,
            custom_from=period1_from,
            custom_to=period1_to,
        )
        payload2 = _build_query_payload(
            timeframe="Custom",
            granularity=granularity,
            group_by=groups,
            custom_from=period2_from,
            custom_to=period2_to,
        )

        token = get_token()
        url = f"{BASE_URL}/{scope}/providers/Microsoft.CostManagement/query?api-version={API_VERSION}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp1 = await client.post(url, json=payload1, headers=headers)
            resp2 = await client.post(url, json=payload2, headers=headers)

        if resp1.status_code != 200:
            return error_response(
                sanitize_error_message(f"Period 1 query failed: {resp1.status_code}")
            )
        if resp2.status_code != 200:
            return error_response(
                sanitize_error_message(f"Period 2 query failed: {resp2.status_code}")
            )

        parsed1 = _parse_query_response(resp1.json())
        parsed2 = _parse_query_response(resp2.json())

        return success_response(
            {
                "period1": {
                    "from": period1_from,
                    "to": period1_to,
                    "rows": parsed1,
                },
                "period2": {
                    "from": period2_from,
                    "to": period2_to,
                    "rows": parsed2,
                },
            },
            scope=scope,
            currency="USD",
            extra_meta={"comparison": True},
        )
    except ValueError as ve:
        return error_response(sanitize_error_message(str(ve)), code="400")
    except Exception as e:
        logger.exception("compare_costs failed")
        return error_response(sanitize_error_message(str(e)))
