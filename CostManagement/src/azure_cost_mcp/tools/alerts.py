"""Alert tools — list and manage cost alerts.

Uses the Azure Cost Management Alerts API:
  https://learn.microsoft.com/en-us/rest/api/cost-management/alerts
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
    """List all cost management alerts for a subscription or resource group.

    Args:
        subscription_id: Azure subscription ID (defaults to AZURE_SUBSCRIPTION_ID env var).
        resource_group: Optional resource group to scope the alert listing.

    Returns:
        JSON array of cost alerts with status, thresholds, and spend details.
    """
    try:
        sub_id = subscription_id or get_subscription_id()
        if resource_group:
            scope = f"subscriptions/{sub_id}/resourceGroups/{resource_group}"
        else:
            scope = f"subscriptions/{sub_id}"

        url = f"{BASE_URL}/{scope}/providers/Microsoft.CostManagement/alerts?api-version={API_VERSION}"
        token = get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )

        if resp.status_code != 200:
            return error_response(
                f"Azure Alerts API error {resp.status_code}: {resp.text}",
                code=str(resp.status_code),
            )

        data = resp.json()
        alerts = [_parse_alert(a) for a in data.get("value", [])]
        return success_response(alerts, scope=scope)
    except Exception as e:
        logger.exception("list_cost_alerts failed")
        return error_response(str(e))


async def dismiss_alert(
    alert_id: str,
    subscription_id: str | None = None,
) -> str:
    """Dismiss a specific cost alert.

    Args:
        alert_id: The full resource ID of the alert, or just the alert name/GUID.
                  If only the name is provided, it will be resolved under the subscription scope.
        subscription_id: Azure subscription ID (defaults to AZURE_SUBSCRIPTION_ID env var).

    Returns:
        JSON confirmation of the dismissed alert.
    """
    try:
        sub_id = subscription_id or get_subscription_id()

        # If alert_id is a full resource path, use it directly; otherwise build it
        if alert_id.startswith("/") or alert_id.startswith("subscriptions/"):
            full_id = alert_id.lstrip("/")
        else:
            full_id = f"subscriptions/{sub_id}/providers/Microsoft.CostManagement/alerts/{alert_id}"

        url = f"{BASE_URL}/{full_id}?api-version={API_VERSION}"
        token = get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # PATCH the alert status to Dismissed
        body = {
            "properties": {
                "status": "Dismissed",
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(url, json=body, headers=headers)

        if resp.status_code != 200:
            return error_response(
                f"Dismiss alert failed {resp.status_code}: {resp.text}",
                code=str(resp.status_code),
            )

        alert = _parse_alert(resp.json())
        return success_response(alert, scope=f"subscriptions/{sub_id}")
    except Exception as e:
        logger.exception("dismiss_alert failed")
        return error_response(str(e))
