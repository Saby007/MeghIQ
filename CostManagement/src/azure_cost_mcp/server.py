"""Azure Cost Management MCP Server.

Registers all cost management tools with FastMCP and exposes them
via the Model Context Protocol.
"""

from __future__ import annotations

import logging
import os
import sys

from mcp.server.fastmcp import FastMCP

from azure_cost_mcp.tools.cost_query import (
    compare_costs,
    query_management_group_costs,
    query_resource_group_costs,
    query_subscription_costs,
)
from azure_cost_mcp.tools.forecast import get_cost_forecast
from azure_cost_mcp.tools.budgets import (
    create_budget,
    delete_budget,
    get_budget,
    list_budgets,
    update_budget,
)
from azure_cost_mcp.tools.alerts import dismiss_alert, list_cost_alerts
from azure_cost_mcp.tools.recommendations import (
    get_recommendation_details,
    list_cost_recommendations,
)
from azure_cost_mcp.tools.anomalies import list_anomalies

# ── Logging ──────────────────────────────────────────────────────────

log_level = os.environ.get("AZURE_COST_MCP_LOG_LEVEL", "WARNING").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.WARNING),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ── MCP Server ───────────────────────────────────────────────────────

mcp = FastMCP(
    "azure-cost-management",
    instructions=(
        "Azure Cost Management MCP Server — query costs, forecasts, budgets, "
        "alerts, optimization recommendations, and anomalies across your Azure "
        "subscriptions. All tools return structured JSON."
    ),
)

# ── Register Cost Query Tools ────────────────────────────────────────


@mcp.tool()
async def query_subscription_costs_tool(
    subscription_id: str = "",
    query_type: str = "ActualCost",
    timeframe: str = "MonthToDate",
    granularity: str = "Daily",
    group_by: str = "ServiceName",
    custom_from: str = "",
    custom_to: str = "",
) -> str:
    """Query costs for an Azure subscription, grouped by dimensions like ServiceName, ResourceGroup, ResourceType, or Tags.

    Args:
        subscription_id: Azure subscription ID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.
        query_type: 'ActualCost' or 'AmortizedCost'.
        timeframe: MonthToDate, BillingMonthToDate, TheLastMonth, TheLastBillingMonth, WeekToDate, or Custom.
        granularity: Daily, Monthly, or None (for totals only).
        group_by: Comma-separated dimensions: ServiceName, ResourceGroup, ResourceType, MeterCategory, ResourceLocation, ChargeType, PublisherType, TagKey:YourTag.
        custom_from: Start date (YYYY-MM-DD) when timeframe='Custom'.
        custom_to: End date (YYYY-MM-DD) when timeframe='Custom'.
    """
    return await query_subscription_costs(
        subscription_id=subscription_id or None,
        query_type=query_type,
        timeframe=timeframe,
        granularity=granularity,
        group_by=group_by,
        custom_from=custom_from or None,
        custom_to=custom_to or None,
    )


@mcp.tool()
async def query_resource_group_costs_tool(
    resource_group: str,
    subscription_id: str = "",
    query_type: str = "ActualCost",
    timeframe: str = "MonthToDate",
    granularity: str = "Daily",
    group_by: str = "ServiceName",
    custom_from: str = "",
    custom_to: str = "",
) -> str:
    """Query costs for a specific Azure resource group.

    Args:
        resource_group: Name of the resource group.
        subscription_id: Azure subscription ID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.
        query_type: 'ActualCost' or 'AmortizedCost'.
        timeframe: MonthToDate, BillingMonthToDate, TheLastMonth, TheLastBillingMonth, WeekToDate, or Custom.
        granularity: Daily, Monthly, or None.
        group_by: Comma-separated dimensions: ServiceName, ResourceType, MeterCategory, etc.
        custom_from: Start date (YYYY-MM-DD) when timeframe='Custom'.
        custom_to: End date (YYYY-MM-DD) when timeframe='Custom'.
    """
    return await query_resource_group_costs(
        resource_group=resource_group,
        subscription_id=subscription_id or None,
        query_type=query_type,
        timeframe=timeframe,
        granularity=granularity,
        group_by=group_by,
        custom_from=custom_from or None,
        custom_to=custom_to or None,
    )


@mcp.tool()
async def query_management_group_costs_tool(
    management_group_id: str,
    query_type: str = "ActualCost",
    timeframe: str = "MonthToDate",
    granularity: str = "Daily",
    group_by: str = "ServiceName",
    custom_from: str = "",
    custom_to: str = "",
) -> str:
    """Query costs for an Azure management group (aggregates all child subscriptions).

    Args:
        management_group_id: The management group ID.
        query_type: 'ActualCost' or 'AmortizedCost'.
        timeframe: MonthToDate, BillingMonthToDate, TheLastMonth, TheLastBillingMonth, WeekToDate, or Custom.
        granularity: Daily, Monthly, or None.
        group_by: Comma-separated dimensions: ServiceName, SubscriptionName, ResourceGroup, etc.
        custom_from: Start date (YYYY-MM-DD) when timeframe='Custom'.
        custom_to: End date (YYYY-MM-DD) when timeframe='Custom'.
    """
    return await query_management_group_costs(
        management_group_id=management_group_id,
        query_type=query_type,
        timeframe=timeframe,
        granularity=granularity,
        group_by=group_by,
        custom_from=custom_from or None,
        custom_to=custom_to or None,
    )


@mcp.tool()
async def compare_costs_tool(
    period1_from: str,
    period1_to: str,
    period2_from: str,
    period2_to: str,
    subscription_id: str = "",
    group_by: str = "ServiceName",
    granularity: str = "None",
) -> str:
    """Compare costs between two time periods to identify spending changes.

    Args:
        period1_from: Start date for period 1 (YYYY-MM-DD).
        period1_to: End date for period 1 (YYYY-MM-DD).
        period2_from: Start date for period 2 (YYYY-MM-DD).
        period2_to: End date for period 2 (YYYY-MM-DD).
        subscription_id: Azure subscription ID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.
        group_by: Comma-separated dimensions to group by.
        granularity: Daily, Monthly, or None (for totals only).
    """
    return await compare_costs(
        period1_from=period1_from,
        period1_to=period1_to,
        period2_from=period2_from,
        period2_to=period2_to,
        subscription_id=subscription_id or None,
        group_by=group_by,
        granularity=granularity,
    )


# ── Register Forecast Tools ─────────────────────────────────────────


@mcp.tool()
async def get_cost_forecast_tool(
    subscription_id: str = "",
    resource_group: str = "",
    granularity: str = "Daily",
    forecast_days: int = 30,
    group_by: str = "",
    include_actual: bool = True,
) -> str:
    """Get cost forecast for a subscription or resource group.

    Args:
        subscription_id: Azure subscription ID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.
        resource_group: Optional resource group name to scope the forecast.
        granularity: Daily or Monthly.
        forecast_days: Number of days to forecast (default 30, max 365).
        group_by: Optional comma-separated dimensions to group forecast by.
        include_actual: Include actual (past) cost alongside forecast (default true).
    """
    return await get_cost_forecast(
        subscription_id=subscription_id or None,
        resource_group=resource_group or None,
        granularity=granularity,
        forecast_days=min(forecast_days, 365),
        group_by=group_by,
        include_actual=include_actual,
    )


# ── Register Budget Tools ───────────────────────────────────────────


@mcp.tool()
async def list_budgets_tool(
    subscription_id: str = "",
    resource_group: str = "",
) -> str:
    """List all cost budgets for a subscription or resource group.

    Args:
        subscription_id: Azure subscription ID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.
        resource_group: Optional resource group scope.
    """
    return await list_budgets(
        subscription_id=subscription_id or None,
        resource_group=resource_group or None,
    )


@mcp.tool()
async def get_budget_tool(
    budget_name: str,
    subscription_id: str = "",
    resource_group: str = "",
) -> str:
    """Get details of a specific budget including utilization percentage.

    Args:
        budget_name: Name of the budget.
        subscription_id: Azure subscription ID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.
        resource_group: Optional resource group scope.
    """
    return await get_budget(
        budget_name=budget_name,
        subscription_id=subscription_id or None,
        resource_group=resource_group or None,
    )


@mcp.tool()
async def create_budget_tool(
    budget_name: str,
    amount: float,
    time_grain: str = "Monthly",
    start_date: str = "",
    end_date: str = "",
    notification_thresholds: str = "80,100",
    contact_emails: str = "",
    subscription_id: str = "",
    resource_group: str = "",
) -> str:
    """Create a new cost budget with notification thresholds.

    Args:
        budget_name: Name for the budget.
        amount: Budget amount in subscription currency.
        time_grain: Monthly, Quarterly, Annually, or BillingMonth.
        start_date: Start date (YYYY-MM-DDT00:00:00Z). Defaults to current month start.
        end_date: End date (YYYY-MM-DDT00:00:00Z). Defaults to 12 months from start.
        notification_thresholds: Comma-separated thresholds, e.g. '80,100,120'. Values >100 use Forecasted type.
        contact_emails: Comma-separated email addresses for notifications.
        subscription_id: Azure subscription ID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.
        resource_group: Optional resource group scope.
    """
    return await create_budget(
        budget_name=budget_name,
        amount=amount,
        time_grain=time_grain,
        start_date=start_date,
        end_date=end_date,
        notification_thresholds=notification_thresholds,
        contact_emails=contact_emails,
        subscription_id=subscription_id or None,
        resource_group=resource_group or None,
    )


@mcp.tool()
async def update_budget_tool(
    budget_name: str,
    amount: float | None = None,
    notification_thresholds: str = "",
    contact_emails: str = "",
    subscription_id: str = "",
    resource_group: str = "",
) -> str:
    """Update an existing budget's amount and/or notification settings.

    Args:
        budget_name: Name of the budget to update.
        amount: New budget amount (leave None to keep current).
        notification_thresholds: New comma-separated thresholds (leave empty to keep current).
        contact_emails: New comma-separated email addresses (leave empty to keep current).
        subscription_id: Azure subscription ID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.
        resource_group: Optional resource group scope.
    """
    return await update_budget(
        budget_name=budget_name,
        amount=amount,
        notification_thresholds=notification_thresholds or None,
        contact_emails=contact_emails or None,
        subscription_id=subscription_id or None,
        resource_group=resource_group or None,
    )


@mcp.tool()
async def delete_budget_tool(
    budget_name: str,
    subscription_id: str = "",
    resource_group: str = "",
) -> str:
    """Delete a cost budget.

    Args:
        budget_name: Name of the budget to delete.
        subscription_id: Azure subscription ID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.
        resource_group: Optional resource group scope.
    """
    return await delete_budget(
        budget_name=budget_name,
        subscription_id=subscription_id or None,
        resource_group=resource_group or None,
    )


# ── Register Alert Tools ────────────────────────────────────────────


@mcp.tool()
async def list_cost_alerts_tool(
    subscription_id: str = "",
    resource_group: str = "",
) -> str:
    """List all cost management alerts for a subscription or resource group.

    Args:
        subscription_id: Azure subscription ID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.
        resource_group: Optional resource group scope.
    """
    return await list_cost_alerts(
        subscription_id=subscription_id or None,
        resource_group=resource_group or None,
    )


@mcp.tool()
async def dismiss_alert_tool(
    alert_id: str,
    subscription_id: str = "",
) -> str:
    """Dismiss a specific cost alert.

    Args:
        alert_id: Full resource ID or name/GUID of the alert to dismiss.
        subscription_id: Azure subscription ID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.
    """
    return await dismiss_alert(
        alert_id=alert_id,
        subscription_id=subscription_id or None,
    )


# ── Register Recommendation Tools ───────────────────────────────────


@mcp.tool()
async def list_cost_recommendations_tool(
    subscription_id: str = "",
) -> str:
    """List Azure Advisor cost optimization recommendations sorted by estimated savings.

    Returns recommendations for right-sizing VMs, purchasing reservations,
    shutting down unused resources, and other cost optimizations.

    Args:
        subscription_id: Azure subscription ID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.
    """
    return await list_cost_recommendations(
        subscription_id=subscription_id or None,
    )


@mcp.tool()
async def get_recommendation_details_tool(
    recommendation_id: str,
    subscription_id: str = "",
) -> str:
    """Get detailed information about a specific Advisor cost recommendation.

    Args:
        recommendation_id: Full resource ID or GUID of the recommendation.
        subscription_id: Azure subscription ID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.
    """
    return await get_recommendation_details(
        recommendation_id=recommendation_id,
        subscription_id=subscription_id or None,
    )


# ── Register Anomaly Detection Tools ────────────────────────────────


@mcp.tool()
async def list_anomalies_tool(
    subscription_id: str = "",
    days_back: int = 30,
) -> str:
    """Detect cost anomalies — unusual spending spikes in your Azure subscription.

    Uses Azure's native Cost Anomaly Detection API if available, otherwise
    falls back to a statistical heuristic (2 std dev above 7-day rolling average).

    Args:
        subscription_id: Azure subscription ID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.
        days_back: Number of days to analyze for anomalies (default 30).
    """
    return await list_anomalies(
        subscription_id=subscription_id or None,
        days_back=days_back,
    )


# ── Entry Point ──────────────────────────────────────────────────────


def main() -> None:
    """Start the Azure Cost Management MCP server."""
    logger.info("Starting Azure Cost Management MCP Server v0.1.0")
    mcp.run()


if __name__ == "__main__":
    main()
