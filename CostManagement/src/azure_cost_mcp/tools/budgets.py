"""Budget tools — list, get, create, update, delete budgets.

Uses the Azure Cost Management Budgets API:
  https://learn.microsoft.com/en-us/rest/api/cost-management/budgets
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from azure_cost_mcp.auth import get_subscription_id, get_token
from azure_cost_mcp.response import error_response, success_response

logger = logging.getLogger(__name__)

API_VERSION = "2023-11-01"
BASE_URL = "https://management.azure.com"


def _budget_url(scope: str, budget_name: str | None = None) -> str:
    base = f"{BASE_URL}/{scope}/providers/Microsoft.CostManagement/budgets"
    if budget_name:
        base += f"/{budget_name}"
    return f"{base}?api-version={API_VERSION}"


def _parse_budget(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract useful fields from a budget resource."""
    props = raw.get("properties", {})
    current = props.get("currentSpend", {})
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "category": props.get("category"),
        "amount": props.get("amount"),
        "timeGrain": props.get("timeGrain"),
        "timePeriod": props.get("timePeriod"),
        "currentSpend": current.get("amount"),
        "currentSpendUnit": current.get("unit"),
        "utilizationPercent": (
            round((current.get("amount", 0) / props["amount"]) * 100, 2)
            if props.get("amount")
            else None
        ),
        "notifications": props.get("notifications"),
        "filter": props.get("filter"),
    }


async def list_budgets(
    subscription_id: str | None = None,
    resource_group: str | None = None,
) -> str:
    """List all budgets for a subscription or resource group.

    Args:
        subscription_id: Azure subscription ID (defaults to AZURE_SUBSCRIPTION_ID env var).
        resource_group: Optional resource group to scope the budget listing.

    Returns:
        JSON array of budgets with name, amount, current spend, and utilization %.
    """
    try:
        sub_id = subscription_id or get_subscription_id()
        if resource_group:
            scope = f"subscriptions/{sub_id}/resourceGroups/{resource_group}"
        else:
            scope = f"subscriptions/{sub_id}"

        url = _budget_url(scope)
        token = get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )

        if resp.status_code != 200:
            return error_response(
                f"Azure Budgets API error {resp.status_code}: {resp.text}",
                code=str(resp.status_code),
            )

        data = resp.json()
        budgets = [_parse_budget(b) for b in data.get("value", [])]
        return success_response(budgets, scope=scope)
    except Exception as e:
        logger.exception("list_budgets failed")
        return error_response(str(e))


async def get_budget(
    budget_name: str,
    subscription_id: str | None = None,
    resource_group: str | None = None,
) -> str:
    """Get details of a specific budget.

    Args:
        budget_name: Name of the budget to retrieve.
        subscription_id: Azure subscription ID (defaults to AZURE_SUBSCRIPTION_ID env var).
        resource_group: Optional resource group scope.

    Returns:
        JSON with budget details including utilization percentage.
    """
    try:
        sub_id = subscription_id or get_subscription_id()
        if resource_group:
            scope = f"subscriptions/{sub_id}/resourceGroups/{resource_group}"
        else:
            scope = f"subscriptions/{sub_id}"

        url = _budget_url(scope, budget_name)
        token = get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )

        if resp.status_code != 200:
            return error_response(
                f"Azure Budgets API error {resp.status_code}: {resp.text}",
                code=str(resp.status_code),
            )

        budget = _parse_budget(resp.json())
        return success_response(budget, scope=scope)
    except Exception as e:
        logger.exception("get_budget failed")
        return error_response(str(e))


async def create_budget(
    budget_name: str,
    amount: float,
    time_grain: str = "Monthly",
    start_date: str = "",
    end_date: str = "",
    notification_thresholds: str = "80,100",
    contact_emails: str = "",
    subscription_id: str | None = None,
    resource_group: str | None = None,
) -> str:
    """Create a new cost budget.

    Args:
        budget_name: Name for the new budget.
        amount: Budget amount in the subscription's currency.
        time_grain: Monthly, Quarterly, Annually, or BillingMonth.
        start_date: Budget start date (YYYY-MM-DDT00:00:00Z). Defaults to current month start.
        end_date: Budget end date (YYYY-MM-DDT00:00:00Z). Defaults to 12 months from start.
        notification_thresholds: Comma-separated threshold percentages (e.g. '80,100,120').
        contact_emails: Comma-separated email addresses for notifications.
        subscription_id: Azure subscription ID (defaults to AZURE_SUBSCRIPTION_ID env var).
        resource_group: Optional resource group scope.

    Returns:
        JSON with the created budget details.
    """
    try:
        sub_id = subscription_id or get_subscription_id()
        if resource_group:
            scope = f"subscriptions/{sub_id}/resourceGroups/{resource_group}"
        else:
            scope = f"subscriptions/{sub_id}"

        from datetime import datetime, timezone

        if not start_date:
            now = datetime.now(timezone.utc)
            start_date = now.replace(day=1).strftime("%Y-%m-%dT00:00:00Z")
        if not end_date:
            from dateutil.relativedelta import relativedelta  # type: ignore

            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end_date = (start_dt + relativedelta(months=12)).strftime("%Y-%m-%dT00:00:00Z")

        # Build notifications
        thresholds = [int(t.strip()) for t in notification_thresholds.split(",") if t.strip()]
        emails = [e.strip() for e in contact_emails.split(",") if e.strip()]
        notifications = {}
        for thresh in thresholds:
            key = f"alert_{thresh}"
            notifications[key] = {
                "enabled": True,
                "operator": "GreaterThan",
                "threshold": thresh,
                "thresholdType": "Actual" if thresh <= 100 else "Forecasted",
                "contactEmails": emails if emails else [],
            }

        body = {
            "properties": {
                "category": "Cost",
                "amount": amount,
                "timeGrain": time_grain,
                "timePeriod": {
                    "startDate": start_date,
                    "endDate": end_date,
                },
                "notifications": notifications,
            }
        }

        url = _budget_url(scope, budget_name)
        token = get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.put(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code not in (200, 201):
            return error_response(
                f"Create budget failed {resp.status_code}: {resp.text}",
                code=str(resp.status_code),
            )

        budget = _parse_budget(resp.json())
        return success_response(budget, scope=scope)
    except Exception as e:
        logger.exception("create_budget failed")
        return error_response(str(e))


async def update_budget(
    budget_name: str,
    amount: float | None = None,
    notification_thresholds: str | None = None,
    contact_emails: str | None = None,
    subscription_id: str | None = None,
    resource_group: str | None = None,
) -> str:
    """Update an existing budget (amount and/or notifications).

    Args:
        budget_name: Name of the budget to update.
        amount: New budget amount (optional).
        notification_thresholds: New comma-separated threshold percentages (optional).
        contact_emails: New comma-separated email addresses (optional).
        subscription_id: Azure subscription ID (defaults to AZURE_SUBSCRIPTION_ID env var).
        resource_group: Optional resource group scope.

    Returns:
        JSON with the updated budget details.
    """
    try:
        sub_id = subscription_id or get_subscription_id()
        if resource_group:
            scope = f"subscriptions/{sub_id}/resourceGroups/{resource_group}"
        else:
            scope = f"subscriptions/{sub_id}"

        url = _budget_url(scope, budget_name)
        token = get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # First get existing budget
        async with httpx.AsyncClient(timeout=30.0) as client:
            get_resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

        if get_resp.status_code != 200:
            return error_response(
                f"Budget '{budget_name}' not found: {get_resp.text}",
                code=str(get_resp.status_code),
            )

        existing = get_resp.json()
        props = existing.get("properties", {})

        if amount is not None:
            props["amount"] = amount

        if notification_thresholds is not None:
            thresholds = [int(t.strip()) for t in notification_thresholds.split(",") if t.strip()]
            emails = (
                [e.strip() for e in contact_emails.split(",") if e.strip()]
                if contact_emails
                else []
            )
            notifications = {}
            for thresh in thresholds:
                key = f"alert_{thresh}"
                notifications[key] = {
                    "enabled": True,
                    "operator": "GreaterThan",
                    "threshold": thresh,
                    "thresholdType": "Actual" if thresh <= 100 else "Forecasted",
                    "contactEmails": emails,
                }
            props["notifications"] = notifications

        existing["properties"] = props

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.put(url, json=existing, headers=headers)

        if resp.status_code not in (200, 201):
            return error_response(
                f"Update budget failed {resp.status_code}: {resp.text}",
                code=str(resp.status_code),
            )

        budget = _parse_budget(resp.json())
        return success_response(budget, scope=scope)
    except Exception as e:
        logger.exception("update_budget failed")
        return error_response(str(e))


async def delete_budget(
    budget_name: str,
    subscription_id: str | None = None,
    resource_group: str | None = None,
) -> str:
    """Delete a budget.

    Args:
        budget_name: Name of the budget to delete.
        subscription_id: Azure subscription ID (defaults to AZURE_SUBSCRIPTION_ID env var).
        resource_group: Optional resource group scope.

    Returns:
        JSON confirmation of deletion.
    """
    try:
        sub_id = subscription_id or get_subscription_id()
        if resource_group:
            scope = f"subscriptions/{sub_id}/resourceGroups/{resource_group}"
        else:
            scope = f"subscriptions/{sub_id}"

        url = _budget_url(scope, budget_name)
        token = get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )

        if resp.status_code not in (200, 204):
            return error_response(
                f"Delete budget failed {resp.status_code}: {resp.text}",
                code=str(resp.status_code),
            )

        return success_response(
            {"deleted": budget_name},
            scope=scope,
        )
    except Exception as e:
        logger.exception("delete_budget failed")
        return error_response(str(e))
