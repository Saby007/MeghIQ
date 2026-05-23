"""Budget tools — list, get, create, update, delete budgets.

Uses the Azure Cost Management Budgets API:
  https://learn.microsoft.com/en-us/rest/api/cost-management/budgets
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from auth import get_subscription_id, get_token
from response import error_response, success_response
from tools.validators import (
    sanitize_error_message,
    validate_budget_name,
    validate_resource_group,
    validate_subscription_id,
)

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


def _validate_scope(subscription_id: str | None, resource_group: str | None) -> tuple[str, str]:
    """Validate and build scope from subscription + optional resource group."""
    sub_id = subscription_id or get_subscription_id()
    sub_id = validate_subscription_id(sub_id)
    if resource_group:
        resource_group = validate_resource_group(resource_group)
        scope = f"subscriptions/{sub_id}/resourceGroups/{resource_group}"
    else:
        scope = f"subscriptions/{sub_id}"
    return sub_id, scope


async def list_budgets(
    subscription_id: str | None = None,
    resource_group: str | None = None,
) -> str:
    """List all budgets for a subscription or resource group."""
    try:
        _, scope = _validate_scope(subscription_id, resource_group)

        url = _budget_url(scope)
        token = get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

        if resp.status_code != 200:
            return error_response(sanitize_error_message(f"Azure Budgets API error {resp.status_code}: {resp.text}"), code=str(resp.status_code))

        data = resp.json()
        budgets = [_parse_budget(b) for b in data.get("value", [])]
        return success_response(budgets, scope=scope)
    except Exception as e:
        logger.exception("list_budgets failed")
        return error_response(sanitize_error_message(str(e)))


async def get_budget(
    budget_name: str,
    subscription_id: str | None = None,
    resource_group: str | None = None,
) -> str:
    """Get details of a specific budget."""
    try:
        _, scope = _validate_scope(subscription_id, resource_group)
        budget_name = validate_budget_name(budget_name)

        url = _budget_url(scope, budget_name)
        token = get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

        if resp.status_code != 200:
            return error_response(sanitize_error_message(f"Azure Budgets API error {resp.status_code}: {resp.text}"), code=str(resp.status_code))

        budget = _parse_budget(resp.json())
        return success_response(budget, scope=scope)
    except Exception as e:
        logger.exception("get_budget failed")
        return error_response(sanitize_error_message(str(e)))


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
    """Create a new cost budget with notification thresholds."""
    try:
        _, scope = _validate_scope(subscription_id, resource_group)
        budget_name = validate_budget_name(budget_name)

        if not start_date:
            now = datetime.now(timezone.utc)
            start_date = now.replace(day=1).strftime("%Y-%m-%dT00:00:00Z")
        if not end_date:
            from dateutil.relativedelta import relativedelta
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end_date = (start_dt + relativedelta(months=12)).strftime("%Y-%m-%dT00:00:00Z")

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
                "timePeriod": {"startDate": start_date, "endDate": end_date},
                "notifications": notifications,
            }
        }

        url = _budget_url(scope, budget_name)
        token = get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.put(
                url,
                json=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )

        if resp.status_code not in (200, 201):
            return error_response(sanitize_error_message(f"Create budget failed {resp.status_code}: {resp.text}"), code=str(resp.status_code))

        budget = _parse_budget(resp.json())
        return success_response(budget, scope=scope)
    except Exception as e:
        logger.exception("create_budget failed")
        return error_response(sanitize_error_message(str(e)))


async def update_budget(
    budget_name: str,
    amount: float | None = None,
    notification_thresholds: str | None = None,
    contact_emails: str | None = None,
    subscription_id: str | None = None,
    resource_group: str | None = None,
) -> str:
    """Update an existing budget (amount and/or notifications)."""
    try:
        _, scope = _validate_scope(subscription_id, resource_group)
        budget_name = validate_budget_name(budget_name)

        url = _budget_url(scope, budget_name)
        token = get_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            get_resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

        if get_resp.status_code != 200:
            return error_response(sanitize_error_message(f"Budget '{budget_name}' not found: {get_resp.text}"), code=str(get_resp.status_code))

        existing = get_resp.json()
        props = existing.get("properties", {})

        if amount is not None:
            props["amount"] = amount

        if notification_thresholds is not None:
            thresholds = [int(t.strip()) for t in notification_thresholds.split(",") if t.strip()]
            emails = [e.strip() for e in contact_emails.split(",") if e.strip()] if contact_emails else []
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
            return error_response(sanitize_error_message(f"Update budget failed {resp.status_code}: {resp.text}"), code=str(resp.status_code))

        budget = _parse_budget(resp.json())
        return success_response(budget, scope=scope)
    except Exception as e:
        logger.exception("update_budget failed")
        return error_response(sanitize_error_message(str(e)))


async def delete_budget(
    budget_name: str,
    subscription_id: str | None = None,
    resource_group: str | None = None,
) -> str:
    """Delete a budget."""
    try:
        _, scope = _validate_scope(subscription_id, resource_group)
        budget_name = validate_budget_name(budget_name)

        url = _budget_url(scope, budget_name)
        token = get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(url, headers={"Authorization": f"Bearer {token}"})

        if resp.status_code not in (200, 204):
            return error_response(sanitize_error_message(f"Delete budget failed {resp.status_code}: {resp.text}"), code=str(resp.status_code))

        return success_response({"deleted": budget_name}, scope=scope)
    except Exception as e:
        logger.exception("delete_budget failed")
        return error_response(sanitize_error_message(str(e)))
