"""Optimization recommendation tools — Azure Advisor cost recommendations.

Uses the Azure Advisor REST API:
  https://learn.microsoft.com/en-us/rest/api/advisor/recommendations
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from auth import get_subscription_id, get_token
from response import error_response, success_response
from tools.http_utils import check_azure_response
from tools.validators import (
    sanitize_error_message,
    validate_azure_resource_id,
    validate_subscription_id,
)

logger = logging.getLogger(__name__)

ADVISOR_API_VERSION = "2023-01-01"
BASE_URL = "https://management.azure.com"


def _parse_recommendation(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract useful fields from an Advisor recommendation."""
    props = raw.get("properties", {})
    impact_map = {"High": 3, "Medium": 2, "Low": 1}
    extended = props.get("extendedProperties", {})

    savings_amount = extended.get("savingsAmount") or extended.get("annualSavingsAmount")
    savings_currency = extended.get("savingsCurrency", "USD")

    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "type": raw.get("type"),
        "category": props.get("category"),
        "impact": props.get("impact"),
        "impactScore": impact_map.get(props.get("impact", ""), 0),
        "impactedField": props.get("impactedField"),
        "impactedValue": props.get("impactedValue"),
        "shortDescription": props.get("shortDescription", {}).get("problem"),
        "solution": props.get("shortDescription", {}).get("solution"),
        "description": props.get("description"),
        "resourceMetadata": props.get("resourceMetadata"),
        "recommendationTypeId": props.get("recommendationTypeId"),
        "lastUpdated": props.get("lastUpdated"),
        "estimatedSavings": savings_amount,
        "savingsCurrency": savings_currency,
        "extendedProperties": extended,
    }


async def list_cost_recommendations(
    subscription_id: str | None = None,
) -> str:
    """List Azure Advisor cost optimization recommendations sorted by estimated savings."""
    try:
        sub_id = (
            validate_subscription_id(subscription_id)
            if subscription_id
            else get_subscription_id()
        )
        scope = f"subscriptions/{sub_id}"

        url = (
            f"{BASE_URL}/{scope}/providers/Microsoft.Advisor/recommendations"
            f"?api-version={ADVISOR_API_VERSION}"
            f"&$filter=Category eq 'Cost'"
        )
        token = get_token()

        all_recommendations: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            while url:
                resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

                err = check_azure_response(resp, api_label="Azure Advisor API")
                if err is not None:
                    return err

                data = resp.json()
                recs = [_parse_recommendation(r) for r in data.get("value", [])]
                all_recommendations.extend(recs)

                url = data.get("nextLink")

        all_recommendations.sort(key=lambda r: float(r.get("estimatedSavings") or 0), reverse=True)

        total_savings = sum(float(r.get("estimatedSavings") or 0) for r in all_recommendations)

        return success_response(
            all_recommendations,
            scope=scope,
            extra_meta={
                "totalEstimatedSavings": round(total_savings, 2),
                "savingsCurrency": "USD",
                "recommendationCount": len(all_recommendations),
            },
        )
    except ValueError as ve:
        return error_response(sanitize_error_message(str(ve)), code="400")
    except Exception as e:
        logger.exception("list_cost_recommendations failed")
        return error_response(sanitize_error_message(str(e)))


async def get_recommendation_details(
    recommendation_id: str,
    subscription_id: str | None = None,
) -> str:
    """Get detailed information about a specific Advisor recommendation."""
    try:
        sub_id = (
            validate_subscription_id(subscription_id)
            if subscription_id
            else get_subscription_id()
        )

        if recommendation_id.startswith("/") or recommendation_id.startswith("subscriptions/"):
            full_id = validate_azure_resource_id(recommendation_id)
        else:
            from tools.validators import _RESOURCE_NAME_RE

            if not _RESOURCE_NAME_RE.match(recommendation_id.strip()):
                raise ValueError("Invalid recommendation_id format")
            full_id = f"subscriptions/{sub_id}/providers/Microsoft.Advisor/recommendations/{recommendation_id.strip()}"

        url = f"{BASE_URL}/{full_id}?api-version={ADVISOR_API_VERSION}"
        token = get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

        err = check_azure_response(resp, api_label="Advisor API")
        if err is not None:
            return err

        rec = _parse_recommendation(resp.json())
        return success_response(rec, scope=f"subscriptions/{sub_id}")
    except ValueError as ve:
        return error_response(sanitize_error_message(str(ve)), code="400")
    except Exception as e:
        logger.exception("get_recommendation_details failed")
        return error_response(sanitize_error_message(str(e)))
