"""Azure service utilization tool — dynamic resource discovery & metric fetching.

Uses Azure Resource Graph to discover resources by service name and Azure
Monitor's metric definitions API to dynamically determine available metrics
per resource type — no hardcoded mappings.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from auth import get_monitor_client, get_subscription_id, get_token
from response import error_response, success_response
from tools.validators import (
    sanitize_error_message,
    sanitize_kql_input,
    validate_subscription_id,
)

logger = logging.getLogger(__name__)

RESOURCE_GRAPH_API_VERSION = "2022-10-01"
RESOURCE_GRAPH_URL = (
    "https://management.azure.com/providers/Microsoft.ResourceGraph/resources"
    f"?api-version={RESOURCE_GRAPH_API_VERSION}"
)
MONITOR_API_VERSION = "2024-02-01"
BASE_URL = "https://management.azure.com"


async def _discover_resource_type(
    service_name: str,
    subscription_id: str,
    token: str,
) -> str | None:
    """Dynamically resolve a service name to an ARM resource type using Resource Graph."""
    search_term = sanitize_kql_input(service_name)

    query = f"""
    Resources
    | where subscriptionId == '{subscription_id}'
    | where type contains '{search_term}'
       or name contains '{search_term}'
    | summarize count() by type
    | order by count_ desc
    | limit 1
    """

    query_body = {
        "subscriptions": [subscription_id],
        "query": query,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            RESOURCE_GRAPH_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=query_body,
        )

    if resp.status_code != 200:
        return None

    data = resp.json().get("data", [])

    # Handle table format or objectArray format
    if isinstance(data, dict):
        rows = data.get("rows", [])
        columns = [c["name"] for c in data.get("columns", [])]
        records = [dict(zip(columns, row)) for row in rows]
    elif isinstance(data, list):
        records = data
    else:
        records = []

    if records:
        return records[0].get("type", "").lower()
    return None


async def _discover_metric_names(
    resource_id: str,
    token: str,
) -> list[str]:
    """Dynamically discover available metric names for a resource using Azure Monitor."""
    url = (
        f"{BASE_URL}{resource_id}/providers/microsoft.insights/metricDefinitions"
        f"?api-version={MONITOR_API_VERSION}"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

    if resp.status_code != 200:
        logger.warning("Metric definitions API returned %d for %s", resp.status_code, resource_id)
        return []

    definitions = resp.json().get("value", [])

    # Prioritize utilization-related metrics
    priority_keywords = [
        "cpu", "memory", "percentage", "percent", "utilization",
        "capacity", "used", "throughput", "requests", "connections",
        "ingress", "egress", "latency", "errors", "count",
    ]

    scored_metrics: list[tuple[int, str]] = []
    for defn in definitions:
        name = defn.get("name", {}).get("value", "")
        display_name = (defn.get("name", {}).get("localizedValue", "") or "").lower()

        # Score by how many priority keywords appear in the name
        score = sum(1 for kw in priority_keywords if kw in name.lower() or kw in display_name)
        scored_metrics.append((score, name))

    # Sort by relevance score descending, take top 8
    scored_metrics.sort(key=lambda x: x[0], reverse=True)
    return [name for score, name in scored_metrics[:8] if score > 0]


async def get_service_utilization(
    service_name: str,
    subscription_id: str | None = None,
) -> str:
    """Get utilization details for a given Azure service in the subscription."""
    try:
        sub_id = subscription_id or get_subscription_id()
        sub_id = validate_subscription_id(sub_id)
        token = get_token()

        # Step 1: Dynamically discover resource type from service name
        resource_type = await _discover_resource_type(service_name, sub_id, token)

        if not resource_type:
            return error_response(
                f"No resources found matching service '{service_name}' "
                f"in subscription. Try a different service name or "
                f"check that resources of this type are deployed."
            )

        # Step 2: Query Resource Graph for resources of this type
        # resource_type is derived from Azure API responses, not user input
        query = f"""
        Resources
        | where type =~ '{resource_type}'
        | where subscriptionId == '{sub_id}'
        | project id, name, type, location, resourceGroup, sku, properties
        | limit 20
        """

        query_body = {
            "subscriptions": [sub_id],
            "query": query,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                RESOURCE_GRAPH_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=query_body,
            )

        if resp.status_code != 200:
            return error_response(
                sanitize_error_message(f"Resource Graph query failed: {resp.status_code}: {resp.text}"),
                code=str(resp.status_code),
            )

        data = resp.json().get("data", [])

        if isinstance(data, dict):
            rows = data.get("rows", [])
            columns = [c["name"] for c in data.get("columns", [])]
            records = [dict(zip(columns, row)) for row in rows]
        elif isinstance(data, list):
            records = data
        else:
            records = []

        if not records:
            return error_response(
                f"No resources of type '{resource_type}' found in subscription."
            )

        # Step 3: For the first resource, discover available metrics dynamically
        first_resource_id = records[0].get("id", "")
        metric_names = await _discover_metric_names(first_resource_id, token)

        # Step 4: Fetch metrics for each resource
        resources: list[dict[str, Any]] = []
        for row in records:
            resource_info: dict[str, Any] = {
                "name": row.get("name", ""),
                "resource_group": row.get("resourceGroup", ""),
                "location": row.get("location", ""),
                "resource_id": row.get("id", ""),
                "sku": str(row.get("sku", "")),
            }

            if metric_names:
                metrics = await _get_resource_metrics(
                    resource_id=row.get("id", ""),
                    metric_names=metric_names,
                    subscription_id=sub_id,
                )
                resource_info["metrics"] = metrics
            else:
                resource_info["metrics"] = {"_note": "No utilization metrics available for this resource type"}

            resources.append(resource_info)

        return success_response(
            {
                "service": service_name,
                "resource_type": resource_type,
                "total_resources": len(resources),
                "discovered_metrics": metric_names,
                "resources": resources,
            },
            scope=f"subscriptions/{sub_id}",
            extra_meta={
                "subscriptionId": sub_id,
                "resourceType": resource_type,
                "metricsDiscovered": len(metric_names),
            },
        )
    except Exception as e:
        logger.exception("get_service_utilization failed")
        return error_response(sanitize_error_message(str(e)))


async def _get_resource_metrics(
    resource_id: str,
    metric_names: list[str],
    subscription_id: str,
) -> dict[str, Any]:
    """Fetch utilization metrics for a specific resource from Azure Monitor."""
    if not metric_names or not resource_id:
        return {}

    monitor_client = get_monitor_client(subscription_id)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start_time = now - timedelta(days=3)

    metrics_data: dict[str, Any] = {}
    try:
        result = await asyncio.to_thread(
            monitor_client.metrics.list,
            resource_uri=resource_id,
            timespan=f"{start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}/{now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            metricnames=",".join(metric_names),
            aggregation="Average,Maximum,Total",
            interval="PT1H",
        )

        for metric in result.value:
            metric_entry: dict[str, Any] = {"unit": str(metric.unit)}
            timeseries_data: list[dict[str, Any]] = []
            for ts in metric.timeseries:
                for dp in ts.data:
                    if dp.average is not None or dp.maximum is not None or dp.total is not None:
                        timeseries_data.append({
                            "timestamp": dp.time_stamp.isoformat() if dp.time_stamp else "",
                            "average": round(dp.average, 2) if dp.average is not None else None,
                            "maximum": round(dp.maximum, 2) if dp.maximum is not None else None,
                            "total": round(dp.total, 2) if dp.total is not None else None,
                        })
            metric_entry["data"] = timeseries_data
            metrics_data[metric.name.value] = metric_entry

    except Exception as e:
        metrics_data["_error"] = f"Could not fetch metrics: {e}"

    return metrics_data
