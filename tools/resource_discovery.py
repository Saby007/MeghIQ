"""Resource discovery via Azure Resource Graph.

Queries Azure Resource Graph to inventory all deployed resource types
in a subscription, and provides dynamic token extraction for matching
resource types to Azure Updates feed categories.

Uses the Azure Resource Graph REST API:
  https://learn.microsoft.com/en-us/rest/api/azureresourcegraph/
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from auth import get_subscription_id, get_token
from response import error_response, success_response
from tools.validators import sanitize_error_message, validate_subscription_id

logger = logging.getLogger(__name__)

RESOURCE_GRAPH_API_VERSION = "2022-10-01"
RESOURCE_GRAPH_URL = (
    "https://management.azure.com/providers/Microsoft.ResourceGraph/resources"
    f"?api-version={RESOURCE_GRAPH_API_VERSION}"
)


def extract_resource_tokens(resource_type: str) -> set[str]:
    """Dynamically extract meaningful tokens from an Azure resource type string."""
    normalised = resource_type.lower().strip()

    # Split on '.' and '/' to get segments
    segments = re.split(r"[./]", normalised)

    # Drop 'microsoft' namespace prefix
    segments = [s for s in segments if s and s != "microsoft"]

    tokens: set[str] = set()

    for segment in segments:
        parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)", segment)

        if parts:
            lower_parts = [p.lower() for p in parts]
            tokens.update(lower_parts)
            # Generate compound pairs from adjacent words
            for i in range(len(lower_parts) - 1):
                compound = f"{lower_parts[i]} {lower_parts[i + 1]}"
                tokens.add(compound)
        else:
            tokens.add(segment)

    # Remove noise tokens
    noise = {"for", "the", "of", "and", "a", "an", "in", "on", "to", "db", "servers",
             "server", "accounts", "account", "services"}
    tokens -= noise

    return tokens


def extract_service_name(resource_type: str) -> str:
    """Extract a human-readable service name from the resource type."""
    normalised = resource_type.lower().strip()
    segments = re.split(r"[./]", normalised)
    segments = [s for s in segments if s and s != "microsoft"]

    words: list[str] = []
    for segment in segments:
        parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)", segment)
        if parts:
            words.extend(parts)
        else:
            words.append(segment)

    return " ".join(w.capitalize() for w in words)


async def discover_deployed_resources(
    subscription_id: str | None = None,
) -> str:
    """Discover all deployed resource types in an Azure subscription."""
    try:
        sub_id = subscription_id or get_subscription_id()
        sub_id = validate_subscription_id(sub_id)
        token = get_token()

        query_body = {
            "subscriptions": [sub_id],
            "query": (
                "Resources "
                "| summarize resourceCount=count() by type, location "
                "| order by resourceCount desc"
            ),
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
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
                sanitize_error_message(f"Resource Graph API error {resp.status_code}: {resp.text}"),
                code=str(resp.status_code),
            )

        data = resp.json()
        raw_data = data.get("data", [])

        # Handle table format or objectArray format
        if isinstance(raw_data, dict):
            rows = raw_data.get("rows", [])
            columns = [c["name"] for c in raw_data.get("columns", [])]
            records = [dict(zip(columns, row)) for row in rows]
        elif isinstance(raw_data, list):
            records = raw_data
        else:
            records = []

        resources: list[dict[str, Any]] = []
        unique_types: dict[str, dict[str, Any]] = {}

        for record in records:
            rtype = record.get("type", "").lower()
            location = record.get("location", "")
            count = record.get("resourceCount", 0)

            resources.append({
                "type": rtype,
                "location": location,
                "count": count,
            })

            if rtype not in unique_types:
                unique_types[rtype] = {
                    "type": rtype,
                    "service_name": extract_service_name(rtype),
                    "tokens": sorted(extract_resource_tokens(rtype)),
                    "total_count": 0,
                    "locations": [],
                }
            unique_types[rtype]["total_count"] += count
            if location and location not in unique_types[rtype]["locations"]:
                unique_types[rtype]["locations"].append(location)

        type_summary = sorted(
            unique_types.values(),
            key=lambda t: t["total_count"],
            reverse=True,
        )

        total_resources = sum(r["count"] for r in resources)

        return success_response(
            {
                "resource_details": resources,
                "type_summary": type_summary,
            },
            scope=f"subscriptions/{sub_id}",
            extra_meta={
                "totalResources": total_resources,
                "uniqueResourceTypes": len(unique_types),
                "subscriptionId": sub_id,
            },
        )
    except Exception as e:
        logger.exception("discover_deployed_resources failed")
        return error_response(sanitize_error_message(str(e)))
