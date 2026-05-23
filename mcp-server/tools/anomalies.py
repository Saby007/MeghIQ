"""Anomaly detection tools — identify cost anomalies.

Uses the Azure Cost Management Cost Anomaly REST API.
Falls back to a cost-spike detection heuristic if the native API is unavailable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from auth import get_subscription_id, get_token
from response import error_response, success_response
from tools.http_utils import check_azure_response, handle_rate_limit
from tools.validators import sanitize_error_message, validate_subscription_id

logger = logging.getLogger(__name__)

BASE_URL = "https://management.azure.com"


async def list_anomalies(
    subscription_id: str | None = None,
    days_back: int = 30,
) -> str:
    """List detected cost anomalies for a subscription.

    Tries the native Azure Cost Anomaly Detection API first, then falls back
    to a heuristic (daily cost spikes > 2 standard deviations from rolling average).
    """
    try:
        sub_id = (
            validate_subscription_id(subscription_id)
            if subscription_id
            else get_subscription_id()
        )
        if days_back <= 0 or days_back > 365:
            raise ValueError("days_back must be between 1 and 365")

        result = await _try_native_anomaly_api(sub_id)
        if result is not None:
            return result

        logger.info("Native anomaly API not available, using heuristic detection")
        return await _heuristic_anomaly_detection(sub_id, days_back)

    except ValueError as ve:
        return error_response(sanitize_error_message(str(ve)), code="400")
    except Exception as e:
        logger.exception("list_anomalies failed")
        return error_response(sanitize_error_message(str(e)))


async def _try_native_anomaly_api(subscription_id: str) -> str | None:
    """Try the native Cost Anomaly Detection API. Returns None if not available."""
    api_version = "2023-11-01"
    scope = f"subscriptions/{subscription_id}"
    url = f"{BASE_URL}/{scope}/providers/Microsoft.CostManagement/anomalies?api-version={api_version}"
    token = get_token()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

        if resp.status_code == 200:
            data = resp.json()
            anomalies = []
            for item in data.get("value", []):
                props = item.get("properties", {})
                anomalies.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "anomalyDate": props.get("anomalyDate"),
                    "expectedValue": props.get("expectedValue"),
                    "actualValue": props.get("actualValue"),
                    "deviation": props.get("deviation"),
                    "category": props.get("category"),
                    "status": props.get("status"),
                    "rootCause": props.get("rootCause"),
                    "resourceGroup": props.get("resourceGroup"),
                    "resourceName": props.get("resourceName"),
                })
            return success_response(
                anomalies,
                scope=scope,
                extra_meta={"source": "AzureCostAnomalyDetection"},
            )

        # 429 (rate-limit) is surfaced explicitly; the caller does not
        # have a heuristic fallback for that condition.
        rl = handle_rate_limit(resp)
        if rl is not None:
            return rl

        if resp.status_code in (404, 400, 501):
            return None

        return error_response(
            sanitize_error_message(f"Anomaly API error {resp.status_code}"),
            code=str(resp.status_code),
        )
    except httpx.HTTPError:
        return None


async def _heuristic_anomaly_detection(subscription_id: str, days_back: int) -> str:
    """Detect cost anomalies using a statistical heuristic.

    Queries daily costs and identifies days where spending exceeds
    the rolling 7-day average by more than 2 standard deviations.
    """
    from tools.cost_services import _build_query_payload, _parse_query_response

    scope = f"subscriptions/{subscription_id}"
    now = datetime.now(timezone.utc)
    custom_from = (now - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00Z")
    custom_to = now.strftime("%Y-%m-%dT00:00:00Z")

    payload = _build_query_payload(
        query_type="ActualCost",
        timeframe="Custom",
        granularity="Daily",
        group_by=[],
        custom_from=custom_from,
        custom_to=custom_to,
    )

    url = f"{BASE_URL}/{scope}/providers/Microsoft.CostManagement/query?api-version=2023-11-01"
    token = get_token()

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )

    err = check_azure_response(resp, api_label="Cost query for anomaly detection")
    if err is not None:
        return err

    rows = _parse_query_response(resp.json())

    daily_costs: list[dict[str, Any]] = []
    for row in rows:
        cost = float(row.get("Cost", 0))
        date_val = row.get("UsageDate") or row.get("BillingPeriod") or row.get("Date", "")
        daily_costs.append({"date": str(date_val), "cost": cost})

    if len(daily_costs) < 8:
        return success_response(
            [],
            scope=scope,
            extra_meta={"source": "heuristic", "message": "Not enough data points for anomaly detection (need at least 8 days)."},
        )

    daily_costs.sort(key=lambda x: x["date"])

    import statistics

    window_size = 7
    anomalies: list[dict[str, Any]] = []

    for i in range(window_size, len(daily_costs)):
        window = [daily_costs[j]["cost"] for j in range(i - window_size, i)]
        mean = statistics.mean(window)
        stdev = statistics.stdev(window) if len(window) > 1 else 0
        current = daily_costs[i]["cost"]

        if stdev > 0 and current > mean + 2 * stdev:
            deviation_pct = round(((current - mean) / mean) * 100, 2) if mean > 0 else 0
            anomalies.append({
                "anomalyDate": daily_costs[i]["date"],
                "actualValue": round(current, 2),
                "expectedValue": round(mean, 2),
                "standardDeviation": round(stdev, 2),
                "deviationPercent": deviation_pct,
                "severity": "High" if deviation_pct > 100 else "Medium" if deviation_pct > 50 else "Low",
            })

    return success_response(
        anomalies,
        scope=scope,
        currency="USD",
        extra_meta={"source": "heuristic", "daysAnalyzed": len(daily_costs), "windowSize": window_size, "thresholdStdDev": 2},
    )
