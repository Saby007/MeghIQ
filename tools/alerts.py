"""Alert tools — list and manage cost alerts.

Uses the Azure Cost Management Alerts API:
  https://learn.microsoft.com/en-us/rest/api/cost-management/alerts
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from auth import get_subscription_id, get_token
from response import error_response, success_response
from tools.validators import (
    sanitize_error_message,
    validate_azure_resource_id,
    validate_resource_group,
    validate_subscription_id,
)

logger = logging.getLogger(__name__)

API_VERSION = "2023-11-01"
BASE_URL = "https://management.azure.com"


def _parse_alert(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract useful fields from an alert resource."""
    props = raw.get("properties", {})
    definition = props.get("definition", {})
    details = props.get("details", {})

    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "type": definition.get("type"),
        "category": definition.get("category"),
        "status": props.get("status"),
        "source": props.get("source"),
        "creationTime": props.get("creationTime"),
        "closeTime": props.get("closeTime"),
        "costEntityId": props.get("costEntityId"),
        "description": props.get("description"),
        "threshold": details.get("threshold"),
        "currentSpend": details.get("currentSpend"),
        "amount": details.get("amount"),
        "unit": details.get("unit"),
        "periodStartDate": details.get("periodStartDate"),
        "contactEmails": details.get("contactEmails"),
        "contactGroups": details.get("contactGroups"),
        "contactRoles": details.get("contactRoles"),
        "overridingAlert": details.get("overridingAlert"),
    }


async def list_cost_alerts(
    subscription_id: str | None = None,
    resource_group: str | None = None,
) -> str:
    """List all cost management alerts for a subscription or resource group."""
    try:
        sub_id = subscription_id or get_subscription_id()
        sub_id = validate_subscription_id(sub_id)
        if resource_group:
            resource_group = validate_resource_group(resource_group)
            scope = f"subscriptions/{sub_id}/resourceGroups/{resource_group}"
        else:
            scope = f"subscriptions/{sub_id}"

        url = f"{BASE_URL}/{scope}/providers/Microsoft.CostManagement/alerts?api-version={API_VERSION}"
        token = get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

        if resp.status_code != 200:
            return error_response(sanitize_error_message(f"Azure Alerts API error {resp.status_code}: {resp.text}"), code=str(resp.status_code))

        data = resp.json()
        alerts = [_parse_alert(a) for a in data.get("value", [])]
        return success_response(alerts, scope=scope)
    except Exception as e:
        logger.exception("list_cost_alerts failed")
        return error_response(sanitize_error_message(str(e)))


async def dismiss_alert(
    alert_id: str,
    subscription_id: str | None = None,
) -> str:
    """Dismiss a specific cost alert."""
    try:
        sub_id = subscription_id or get_subscription_id()
        sub_id = validate_subscription_id(sub_id)

        if alert_id.startswith("/") or alert_id.startswith("subscriptions/"):
            full_id = validate_azure_resource_id(alert_id)
        else:
            full_id = validate_azure_resource_id(
                f"subscriptions/{sub_id}/providers/Microsoft.CostManagement/alerts/{alert_id}"
            )

        url = f"{BASE_URL}/{full_id}?api-version={API_VERSION}"
        token = get_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        body = {"properties": {"status": "Dismissed"}}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(url, json=body, headers=headers)

        if resp.status_code != 200:
            return error_response(sanitize_error_message(f"Dismiss alert failed {resp.status_code}: {resp.text}"), code=str(resp.status_code))

        alert = _parse_alert(resp.json())
        return success_response(alert, scope=f"subscriptions/{sub_id}")
    except Exception as e:
        logger.exception("dismiss_alert failed")
        return error_response(sanitize_error_message(str(e)))
