"""MeghIQ MCP Server — Azure Cost Optimization Tools.

A Model Context Protocol (MCP) server that exposes tools for Azure cost
management, utilization analysis, Azure Updates intelligence, and more.
"""

from __future__ import annotations

import argparse
import hmac
import logging
import os
import sys
from typing import Annotated, Literal

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import Field

# Ensure the project root is on the path for local imports
sys.path.insert(0, os.path.dirname(__file__))

load_dotenv()

from tools.cost_services import (
    compare_costs,
    query_management_group_costs,
    query_resource_group_costs,
    query_subscription_costs,
)
from tools.forecast import get_cost_forecast
from tools.budgets import (
    create_budget,
    delete_budget,
    get_budget,
    list_budgets,
    update_budget,
)
from tools.alerts import dismiss_alert, list_cost_alerts
from tools.recommendations import (
    get_recommendation_details,
    list_cost_recommendations,
)
from tools.anomalies import list_anomalies
from tools.azure_updates import (
    get_azure_update_details,
    list_all_azure_updates,
)
from tools.update_intelligence import (
    drill_down_updates,
    get_personalized_updates,
)
from tools.azure_updates_history import search_azure_updates_history
from tools.pdf_report import generate_report
from tools.utilization import (
    get_service_utilization as _get_service_utilization,
    get_utilization_metrics as _get_utilization_metrics,
)
from telemetry import RequestContextFilter, instrument, telemetry_snapshot

# ── Logging ──────────────────────────────────────────────────────────

log_level = os.environ.get("MEGHIQ_LOG_LEVEL", "WARNING").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.WARNING),
    format="%(asctime)s [%(levelname)s] [req=%(request_id)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
# Attach request-id filter to the root handler so log lines emitted from
# anywhere inside a tool call carry the correlation id.
for _h in logging.getLogger().handlers:
    _h.addFilter(RequestContextFilter())
logger = logging.getLogger(__name__)

# One-shot startup warning if /metrics is unauthenticated. The endpoint
# exposes per-tool counters which are not secret in themselves but reveal
# usage patterns; require a token in production by setting
# MEGHIQ_METRICS_TOKEN to a non-empty value.
if not os.environ.get("MEGHIQ_METRICS_TOKEN", "").strip():
    logger.warning(
        "/metrics endpoint is UNAUTHENTICATED. "
        "Set MEGHIQ_METRICS_TOKEN to require Authorization: Bearer <token>."
    )

# ── MCP Server ───────────────────────────────────────────────────────

# Binding to 0.0.0.0 is intentional: the server is expected to run inside
# an Azure App Service / container where the platform terminates ingress
# and the container itself must listen on all interfaces. Override with
# MCP_HOST=127.0.0.1 for local-only development.
_host = os.environ.get("MCP_HOST", "0.0.0.0")  # nosec B104
_port = int(os.environ.get("MCP_SERVER_PORT", "8000"))

mcp = FastMCP(
    "MeghIQ Cost Optimizer",
    host=_host,
    port=_port,
    stateless_http=True,
    instructions=(
        "MeghIQ Azure Cost Optimization MCP Server — query costs, forecasts, "
        "budgets, alerts, optimization recommendations, anomalies, utilization "
        "metrics, and personalised Azure Updates Intelligence across your "
        "Azure subscriptions. All tools return structured JSON. "
        "For Azure Updates, use get_personalized_azure_updates first for a "
        "compact service-grouped summary, then drill_down_azure_updates to "
        "expand any section, service, or status on demand."
    ),
)

# ── Health Check Endpoints ───────────────────────────────────────────

from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@mcp.custom_route("/", methods=["GET"])
async def root_health(request: Request) -> Response:
    return JSONResponse({"status": "ok", "service": "meghiq-mcp"})


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> Response:
    return JSONResponse({"status": "ok", "service": "meghiq-mcp"})


@mcp.custom_route("/metrics", methods=["GET"])
async def metrics(request: Request) -> Response:
    """Expose in-memory tool-call counters.

    Auth (optional, off by default):
        Set ``MEGHIQ_METRICS_TOKEN`` to a non-empty value to require
        ``Authorization: Bearer <token>`` on every request. When the env
        var is unset the endpoint is open (a one-shot WARNING is logged
        at startup so production deployments cannot enable it accidentally).

    Content negotiation:
        * ``Accept: text/plain`` (or ``application/openmetrics-text``)
          returns the Prometheus exposition format suitable for scraping
          by Prometheus / Grafana Agent / OpenTelemetry collector.
        * Anything else (including the default) returns JSON.
    """
    # ── Auth ────────────────────────────────────────────────────────
    expected = os.environ.get("MEGHIQ_METRICS_TOKEN", "").strip()
    if expected:
        provided = request.headers.get("authorization", "")
        prefix = "Bearer "
        ok = (
            provided.startswith(prefix)
            and hmac.compare_digest(provided[len(prefix):], expected)
        )
        if not ok:
            # Do NOT leak which half (header/token) was wrong — return a
            # uniform 401 so the endpoint cannot be probed.
            return Response(status_code=401, content="unauthorized")

    snapshot = telemetry_snapshot()

    # ── Content negotiation ─────────────────────────────────────────
    accept = request.headers.get("accept", "").lower()
    if "text/plain" in accept or "openmetrics" in accept:
        return Response(
            content=_render_prometheus(snapshot),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )
    return JSONResponse(snapshot)


def _render_prometheus(snapshot: dict) -> str:
    """Render the telemetry snapshot in Prometheus exposition format.

    Emits four metric families:
      meghiq_tool_calls_total       (counter, per tool)
      meghiq_tool_errors_total      (counter, per tool)
      meghiq_tool_latency_ms_avg    (gauge, per tool)
      meghiq_tool_latency_ms_max    (gauge, per tool)
    """
    lines: list[str] = []

    def _emit_family(name: str, kind: str, help_text: str, samples: list[tuple[str, float]]) -> None:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {kind}")
        for tool_name, value in samples:
            # Escape backslashes and double-quotes in label values per spec.
            safe = tool_name.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{name}{{tool="{safe}"}} {value}')

    tools = snapshot.get("tools", {}) or {}
    calls = [(t, m.get("calls", 0)) for t, m in tools.items()]
    errors = [(t, m.get("errors", 0)) for t, m in tools.items()]
    avg_lat = [(t, m.get("avg_latency_ms", 0.0)) for t, m in tools.items()]
    max_lat = [(t, m.get("max_latency_ms", 0.0)) for t, m in tools.items()]

    _emit_family(
        "meghiq_tool_calls_total",
        "counter",
        "Total successful + failed invocations per tool.",
        calls,
    )
    _emit_family(
        "meghiq_tool_errors_total",
        "counter",
        "Invocations that returned an error envelope or raised.",
        errors,
    )
    _emit_family(
        "meghiq_tool_latency_ms_avg",
        "gauge",
        "Average wall-clock latency per tool in milliseconds.",
        avg_lat,
    )
    _emit_family(
        "meghiq_tool_latency_ms_max",
        "gauge",
        "Peak wall-clock latency per tool in milliseconds.",
        max_lat,
    )

    # Trailing newline is required by the Prometheus parser.
    return "\n".join(lines) + "\n"


# ── Shared parameter constraints ─────────────────────────────────────
#
# These Annotated aliases are reused across tool signatures so the MCP
# client receives a precise JSON schema (pattern, bounds, enum, examples)
# for every argument. FastMCP forwards Pydantic Field metadata to the
# tool-discovery payload.

_UUID_OR_EMPTY = r"^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})?$"
_RG_OR_EMPTY = r"^[a-zA-Z0-9._\-()]{0,90}$"
_BUDGET_NAME = r"^[a-zA-Z0-9_\-]{1,63}$"
_MG_ID = r"^[a-zA-Z0-9_\-.()]{1,90}$"
_DATE_OR_EMPTY = r"^(\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?Z?)?)?$"
_INTERVAL_OR_EMPTY = r"^(PT\d+[MHS]|P\d+D)?$"
_RESOURCE_ID = r"^/subscriptions/[0-9a-fA-F\-]{36}/.+"

QueryType = Literal["ActualCost", "AmortizedCost"]
Timeframe = Literal[
    "MonthToDate",
    "BillingMonthToDate",
    "TheLastMonth",
    "TheLastBillingMonth",
    "WeekToDate",
    "Custom",
]
Granularity = Literal["Daily", "Monthly", "None"]
ForecastGranularity = Literal["Daily", "Monthly"]
TimeGrain = Literal["Monthly", "Quarterly", "Annually", "BillingMonth"]
ReportType = Literal["full", "executive"]


SubscriptionId = Annotated[
    str,
    Field(
        default="",
        description="Azure subscription UUID. Leave empty to use AZURE_SUBSCRIPTION_ID env var.",
        pattern=_UUID_OR_EMPTY,
        examples=["00000000-0000-0000-0000-000000000000"],
    ),
]
ResourceGroupOpt = Annotated[
    str,
    Field(
        default="",
        description="Optional Azure resource group name (max 90 chars).",
        pattern=_RG_OR_EMPTY,
    ),
]


# ── Cost Query Tools ─────────────────────────────────────────────────


@mcp.tool()
@instrument()
async def query_subscription_costs_tool(
    subscription_id: SubscriptionId = "",
    query_type: Annotated[
        QueryType,
        Field(description="Cost view: ActualCost (billed) or AmortizedCost (reservation-amortised)."),
    ] = "ActualCost",
    timeframe: Annotated[
        Timeframe,
        Field(description="Predefined window or 'Custom' (requires custom_from/custom_to)."),
    ] = "MonthToDate",
    granularity: Annotated[
        Granularity,
        Field(description="Bucket size for time series, or 'None' for totals only."),
    ] = "Daily",
    group_by: Annotated[
        str,
        Field(
            description=(
                "Comma-separated dimensions: ServiceName, ResourceGroup, "
                "ResourceType, MeterCategory, ResourceLocation, ChargeType, "
                "PublisherType, TagKey:YourTag."
            ),
            max_length=200,
        ),
    ] = "ServiceName",
    custom_from: Annotated[
        str,
        Field(description="Start date YYYY-MM-DD when timeframe='Custom'.", pattern=_DATE_OR_EMPTY),
    ] = "",
    custom_to: Annotated[
        str,
        Field(description="End date YYYY-MM-DD when timeframe='Custom'.", pattern=_DATE_OR_EMPTY),
    ] = "",
) -> str:
    """Query costs for an Azure subscription, grouped by dimensions like ServiceName, ResourceGroup, ResourceType, or Tags."""
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
@instrument()
async def query_resource_group_costs_tool(
    resource_group: Annotated[
        str,
        Field(description="Name of the resource group (required).", pattern=r"^[a-zA-Z0-9._\-()]{1,90}$"),
    ],
    subscription_id: SubscriptionId = "",
    query_type: Annotated[QueryType, Field(description="ActualCost or AmortizedCost.")] = "ActualCost",
    timeframe: Annotated[Timeframe, Field(description="Predefined window or 'Custom'.")] = "MonthToDate",
    granularity: Annotated[Granularity, Field(description="Daily, Monthly, or None.")] = "Daily",
    group_by: Annotated[
        str,
        Field(
            description="Comma-separated dimensions: ServiceName, ResourceType, MeterCategory, etc.",
            max_length=200,
        ),
    ] = "ServiceName",
    custom_from: Annotated[
        str, Field(description="Start date YYYY-MM-DD when timeframe='Custom'.", pattern=_DATE_OR_EMPTY)
    ] = "",
    custom_to: Annotated[
        str, Field(description="End date YYYY-MM-DD when timeframe='Custom'.", pattern=_DATE_OR_EMPTY)
    ] = "",
) -> str:
    """Query costs for a specific Azure resource group."""
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
@instrument()
async def query_management_group_costs_tool(
    management_group_id: Annotated[
        str,
        Field(description="The management group ID.", pattern=_MG_ID),
    ],
    query_type: Annotated[QueryType, Field(description="ActualCost or AmortizedCost.")] = "ActualCost",
    timeframe: Annotated[Timeframe, Field(description="Predefined window or 'Custom'.")] = "MonthToDate",
    granularity: Annotated[Granularity, Field(description="Daily, Monthly, or None.")] = "Daily",
    group_by: Annotated[
        str,
        Field(
            description="Comma-separated dimensions: ServiceName, SubscriptionName, ResourceGroup, etc.",
            max_length=200,
        ),
    ] = "ServiceName",
    custom_from: Annotated[
        str, Field(description="Start date YYYY-MM-DD when timeframe='Custom'.", pattern=_DATE_OR_EMPTY)
    ] = "",
    custom_to: Annotated[
        str, Field(description="End date YYYY-MM-DD when timeframe='Custom'.", pattern=_DATE_OR_EMPTY)
    ] = "",
) -> str:
    """Query costs for an Azure management group (aggregates all child subscriptions)."""
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
@instrument()
async def compare_costs_tool(
    period1_from: Annotated[str, Field(description="Start date for period 1 (YYYY-MM-DD).", pattern=_DATE_OR_EMPTY)],
    period1_to: Annotated[str, Field(description="End date for period 1 (YYYY-MM-DD).", pattern=_DATE_OR_EMPTY)],
    period2_from: Annotated[str, Field(description="Start date for period 2 (YYYY-MM-DD).", pattern=_DATE_OR_EMPTY)],
    period2_to: Annotated[str, Field(description="End date for period 2 (YYYY-MM-DD).", pattern=_DATE_OR_EMPTY)],
    subscription_id: SubscriptionId = "",
    group_by: Annotated[
        str, Field(description="Comma-separated dimensions to group by.", max_length=200)
    ] = "ServiceName",
    granularity: Annotated[Granularity, Field(description="Daily, Monthly, or None (totals).")] = "None",
) -> str:
    """Compare costs between two time periods to identify spending changes."""
    return await compare_costs(
        period1_from=period1_from,
        period1_to=period1_to,
        period2_from=period2_from,
        period2_to=period2_to,
        subscription_id=subscription_id or None,
        group_by=group_by,
        granularity=granularity,
    )


# ── Forecast Tools ───────────────────────────────────────────────────


@mcp.tool()
@instrument()
async def get_cost_forecast_tool(
    subscription_id: SubscriptionId = "",
    resource_group: ResourceGroupOpt = "",
    granularity: Annotated[
        ForecastGranularity, Field(description="Daily or Monthly forecast bucket.")
    ] = "Daily",
    forecast_days: Annotated[
        int,
        Field(description="Number of days to forecast (1-365).", ge=1, le=365),
    ] = 30,
    group_by: Annotated[
        str,
        Field(description="Optional comma-separated dimensions to group forecast by.", max_length=200),
    ] = "",
    include_actual: Annotated[
        bool, Field(description="Include actual (past) cost alongside forecast.")
    ] = True,
) -> str:
    """Get cost forecast for a subscription or resource group."""
    return await get_cost_forecast(
        subscription_id=subscription_id or None,
        resource_group=resource_group or None,
        granularity=granularity,
        forecast_days=forecast_days,
        group_by=group_by,
        include_actual=include_actual,
    )


# ── Budget Tools ─────────────────────────────────────────────────────


@mcp.tool()
@instrument()
async def list_budgets_tool(
    subscription_id: SubscriptionId = "",
    resource_group: ResourceGroupOpt = "",
) -> str:
    """List all cost budgets for a subscription or resource group."""
    return await list_budgets(
        subscription_id=subscription_id or None,
        resource_group=resource_group or None,
    )


@mcp.tool()
@instrument()
async def get_budget_tool(
    budget_name: Annotated[
        str, Field(description="Name of the budget.", pattern=_BUDGET_NAME)
    ],
    subscription_id: SubscriptionId = "",
    resource_group: ResourceGroupOpt = "",
) -> str:
    """Get details of a specific budget including utilization percentage."""
    return await get_budget(
        budget_name=budget_name,
        subscription_id=subscription_id or None,
        resource_group=resource_group or None,
    )


@mcp.tool()
@instrument()
async def create_budget_tool(
    budget_name: Annotated[
        str, Field(description="Name for the new budget.", pattern=_BUDGET_NAME)
    ],
    amount: Annotated[
        float,
        Field(description="Budget amount in subscription currency.", gt=0.0, le=1e12),
    ],
    time_grain: Annotated[
        TimeGrain, Field(description="Budget reset cadence.")
    ] = "Monthly",
    start_date: Annotated[
        str,
        Field(
            description="Start date (YYYY-MM-DDT00:00:00Z). Defaults to current month start.",
            pattern=_DATE_OR_EMPTY,
        ),
    ] = "",
    end_date: Annotated[
        str,
        Field(
            description="End date (YYYY-MM-DDT00:00:00Z). Defaults to 12 months from start.",
            pattern=_DATE_OR_EMPTY,
        ),
    ] = "",
    notification_thresholds: Annotated[
        str,
        Field(
            description="Comma-separated thresholds, e.g. '80,100,120'. Values >100 use Forecasted type.",
            pattern=r"^(\d{1,3}(,\d{1,3})*)?$",
        ),
    ] = "80,100",
    contact_emails: Annotated[
        str,
        Field(description="Comma-separated email addresses for notifications.", max_length=2000),
    ] = "",
    subscription_id: SubscriptionId = "",
    resource_group: ResourceGroupOpt = "",
) -> str:
    """Create a new cost budget with notification thresholds."""
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
@instrument()
async def update_budget_tool(
    budget_name: Annotated[str, Field(description="Name of the budget to update.", pattern=_BUDGET_NAME)],
    amount: Annotated[
        float | None,
        Field(
            description="New budget amount (leave None to keep current).",
            default=None,
            gt=0.0,
            le=1e12,
        ),
    ] = None,
    notification_thresholds: Annotated[
        str,
        Field(
            description="New comma-separated thresholds (leave empty to keep current).",
            pattern=r"^(\d{1,3}(,\d{1,3})*)?$",
        ),
    ] = "",
    contact_emails: Annotated[
        str,
        Field(description="New comma-separated emails (leave empty to keep current).", max_length=2000),
    ] = "",
    subscription_id: SubscriptionId = "",
    resource_group: ResourceGroupOpt = "",
) -> str:
    """Update an existing budget's amount and/or notification settings."""
    return await update_budget(
        budget_name=budget_name,
        amount=amount,
        notification_thresholds=notification_thresholds or None,
        contact_emails=contact_emails or None,
        subscription_id=subscription_id or None,
        resource_group=resource_group or None,
    )


@mcp.tool()
@instrument()
async def delete_budget_tool(
    budget_name: Annotated[str, Field(description="Name of the budget to delete.", pattern=_BUDGET_NAME)],
    subscription_id: SubscriptionId = "",
    resource_group: ResourceGroupOpt = "",
) -> str:
    """Delete a cost budget."""
    return await delete_budget(
        budget_name=budget_name,
        subscription_id=subscription_id or None,
        resource_group=resource_group or None,
    )


# ── Alert Tools ──────────────────────────────────────────────────────


@mcp.tool()
@instrument()
async def list_cost_alerts_tool(
    subscription_id: SubscriptionId = "",
    resource_group: ResourceGroupOpt = "",
) -> str:
    """List all cost management alerts for a subscription or resource group."""
    return await list_cost_alerts(
        subscription_id=subscription_id or None,
        resource_group=resource_group or None,
    )


@mcp.tool()
@instrument()
async def dismiss_alert_tool(
    alert_id: Annotated[
        str,
        Field(
            description="Full resource ID or name/GUID of the alert to dismiss.",
            min_length=1,
            max_length=512,
        ),
    ],
    subscription_id: SubscriptionId = "",
) -> str:
    """Dismiss a specific cost alert."""
    return await dismiss_alert(
        alert_id=alert_id,
        subscription_id=subscription_id or None,
    )


# ── Recommendation Tools ────────────────────────────────────────────


@mcp.tool()
@instrument()
async def list_cost_recommendations_tool(
    subscription_id: SubscriptionId = "",
) -> str:
    """List Azure Advisor cost optimization recommendations sorted by estimated savings.

    Returns recommendations for right-sizing VMs, purchasing reservations,
    shutting down unused resources, and other cost optimizations.
    """
    return await list_cost_recommendations(
        subscription_id=subscription_id or None,
    )


@mcp.tool()
@instrument()
async def get_recommendation_details_tool(
    recommendation_id: Annotated[
        str,
        Field(
            description="Full resource ID or GUID of the recommendation.",
            min_length=1,
            max_length=512,
        ),
    ],
    subscription_id: SubscriptionId = "",
) -> str:
    """Get detailed information about a specific Advisor cost recommendation."""
    return await get_recommendation_details(
        recommendation_id=recommendation_id,
        subscription_id=subscription_id or None,
    )


# ── Anomaly Detection Tools ─────────────────────────────────────────


@mcp.tool()
@instrument()
async def list_anomalies_tool(
    subscription_id: SubscriptionId = "",
    days_back: Annotated[
        int,
        Field(description="Number of days to analyze for anomalies (1-365).", ge=1, le=365),
    ] = 30,
) -> str:
    """Detect cost anomalies — unusual spending spikes in your Azure subscription.

    Uses Azure's native Cost Anomaly Detection API if available, otherwise
    falls back to a statistical heuristic (2 std dev above 7-day rolling average).
    """
    return await list_anomalies(
        subscription_id=subscription_id or None,
        days_back=days_back,
    )


# ── Utilization Tools ────────────────────────────────────────────────


@mcp.tool()
@instrument()
async def get_service_utilization_tool(
    service_name: Annotated[
        str,
        Field(
            description="Azure service to query (e.g., 'Storage', 'Virtual Machines', 'SQL', 'Cosmos DB', 'AKS').",
            min_length=1,
            max_length=120,
        ),
    ],
    subscription_id: SubscriptionId = "",
    start_time: Annotated[
        str,
        Field(
            description="Optional ISO-8601 UTC start (e.g., '2026-05-01T00:00:00Z').",
            pattern=_DATE_OR_EMPTY,
        ),
    ] = "",
    end_time: Annotated[
        str,
        Field(description="Optional ISO-8601 UTC end. Defaults to now.", pattern=_DATE_OR_EMPTY),
    ] = "",
    interval: Annotated[
        str,
        Field(
            description="Optional Azure Monitor time grain (PT5M, PT1H, PT6H, PT12H, P1D).",
            pattern=_INTERVAL_OR_EMPTY,
        ),
    ] = "",
    metric_namespace: Annotated[
        str,
        Field(
            description=(
                "Optional metric namespace, e.g. "
                "'Microsoft.Storage/storageAccounts/blobServices' for blob metrics."
            ),
            max_length=200,
        ),
    ] = "",
) -> str:
    """Get utilization details of an Azure service in the subscription.

    Dynamically discovers resource types and available metrics — no hardcoded
    mappings. Defaults to the last 3 days when no time window is supplied;
    max window is 93 days.
    """
    return await _get_service_utilization(
        service_name=service_name,
        subscription_id=subscription_id or None,
        start_time=start_time or None,
        end_time=end_time or None,
        interval=interval or None,
        metric_namespace=metric_namespace or None,
    )


@mcp.tool()
@instrument()
async def get_utilization_metrics_tool(
    resource_id: Annotated[
        str,
        Field(
            description=(
                "Full ARM resource ID "
                "(e.g., '/subscriptions/<sub>/resourceGroups/<rg>/providers/...')."
            ),
            pattern=_RESOURCE_ID,
            min_length=1,
            max_length=1024,
        ),
    ],
    metric_names: Annotated[
        list[str] | None,
        Field(
            description=(
                "Optional explicit list of metric names. When omitted and a "
                "namespace was specified, returns ALL metrics in that namespace "
                "(capped at max_metrics_per_namespace)."
            ),
            default=None,
            max_length=50,
        ),
    ] = None,
    metric_namespace: Annotated[
        str,
        Field(description="Single metric namespace.", max_length=200),
    ] = "",
    metric_namespaces: Annotated[
        list[str] | None,
        Field(
            description="Multiple metric namespaces to query in one call.",
            default=None,
            max_length=20,
        ),
    ] = None,
    start_time: Annotated[
        str,
        Field(description="Optional ISO-8601 UTC start (max 93 days back).", pattern=_DATE_OR_EMPTY),
    ] = "",
    end_time: Annotated[
        str,
        Field(description="Optional ISO-8601 UTC end. Defaults to now.", pattern=_DATE_OR_EMPTY),
    ] = "",
    interval: Annotated[
        str,
        Field(
            description="Optional Azure Monitor time grain (auto-picked from window).",
            pattern=_INTERVAL_OR_EMPTY,
        ),
    ] = "",
    subscription_id: SubscriptionId = "",
    include_child_namespaces: Annotated[
        bool,
        Field(
            description=(
                "When True and no namespace specified, enumerate Platform "
                "namespaces on the resource."
            )
        ),
    ] = False,
    include_custom_namespaces: Annotated[
        bool,
        Field(description="When auto-enumerating, also include Custom/Qos namespaces."),
    ] = False,
    max_metrics_per_namespace: Annotated[
        int,
        Field(description="Cap on metrics returned per namespace.", ge=1, le=200),
    ] = 20,
) -> str:
    """Fetch Azure Monitor metrics for a specific resource by resource_id.

    Use this tool when you already know the resource and need full control
    over the metrics window, time grain, metric list, and metric namespace.

    Supports child namespaces (e.g., a Storage Account's blob metrics live
    under 'Microsoft.Storage/storageAccounts/blobServices').
    """
    return await _get_utilization_metrics(
        resource_id=resource_id,
        metric_names=metric_names,
        metric_namespace=metric_namespace or None,
        metric_namespaces=metric_namespaces,
        start_time=start_time or None,
        end_time=end_time or None,
        interval=interval or None,
        subscription_id=subscription_id or None,
        include_child_namespaces=include_child_namespaces,
        include_custom_namespaces=include_custom_namespaces,
        max_metrics_per_namespace=max_metrics_per_namespace,
    )


# ── Azure Updates Intelligence Tools ────────────────────────────────


@mcp.tool()
@instrument()
async def get_personalized_azure_updates_tool(
    subscription_id: SubscriptionId = "",
    highlights_per_section: Annotated[
        int, Field(description="Critical highlights to expand per section.", ge=1, le=20)
    ] = 3,
    highlights_per_group: Annotated[
        int, Field(description="Top updates to expand per service group.", ge=1, le=10)
    ] = 1,
    urgency_weight: Annotated[
        float, Field(description="Weight for urgency vs relevance (0.0-1.0).", ge=0.0, le=1.0)
    ] = 0.4,
    export_csv: Annotated[
        bool, Field(description="Export all relevant updates to a CSV file.")
    ] = True,
    csv_output_dir: Annotated[
        str,
        Field(
            description="Directory for the CSV file. Leave empty for current working directory.",
            max_length=1024,
        ),
    ] = "",
) -> str:
    """Get a personalised Azure Updates digest — compact, service-grouped summary.

    Phase 1 of the two-phase updates workflow. After reviewing the summary,
    use drill_down_azure_updates to expand any section, service, or status.
    """
    return await get_personalized_updates(
        subscription_id=subscription_id or None,
        highlights_per_section=highlights_per_section,
        highlights_per_group=highlights_per_group,
        urgency_weight=urgency_weight,
        export_csv=export_csv,
        csv_output_dir=csv_output_dir or None,
    )


@mcp.tool()
@instrument()
async def drill_down_azure_updates_tool(
    subscription_id: SubscriptionId = "",
    section: Annotated[
        str, Field(description="Filter by section name (partial match).", max_length=120)
    ] = "",
    service: Annotated[
        str, Field(description="Filter by service name/category (partial match).", max_length=120)
    ] = "",
    status: Annotated[
        str, Field(description="Filter by update status (partial match).", max_length=120)
    ] = "",
    min_relevance: Annotated[
        float, Field(description="Minimum relevance score threshold.", ge=0.0, le=1.0)
    ] = 0.15,
    max_results: Annotated[
        int, Field(description="Maximum updates to return.", ge=1, le=500)
    ] = 25,
    urgency_weight: Annotated[
        float, Field(description="Weight for urgency vs relevance (0.0-1.0).", ge=0.0, le=1.0)
    ] = 0.4,
) -> str:
    """Drill down into a specific slice of the Azure Updates digest.

    Phase 2 of the two-phase updates workflow. All filters are case-insensitive
    partial matches combined with AND logic.
    """
    return await drill_down_updates(
        subscription_id=subscription_id or None,
        section=section or None,
        service=service or None,
        status=status or None,
        min_relevance=min_relevance,
        max_results=max_results,
        urgency_weight=urgency_weight,
    )


@mcp.tool()
@instrument()
async def list_all_azure_updates_tool(
    category: Annotated[
        str, Field(description="Optional category filter (e.g. 'Virtual Machines').", max_length=120)
    ] = "",
    status: Annotated[
        str, Field(description="Optional status filter (e.g. 'Launched', 'In preview').", max_length=120)
    ] = "",
    search: Annotated[
        str, Field(description="Optional keyword search across title and description.", max_length=200)
    ] = "",
    max_results: Annotated[
        int, Field(description="Maximum number of updates to return.", ge=1, le=500)
    ] = 50,
) -> str:
    """List all Azure Updates from the official RSS feed (unfiltered by environment)."""
    return await list_all_azure_updates(
        category=category or None,
        status=status or None,
        search=search or None,
        max_results=max_results,
    )


@mcp.tool()
@instrument()
async def get_azure_update_details_tool(
    update_id: Annotated[
        str,
        Field(
            description="The unique GUID identifier of the update.",
            min_length=1,
            max_length=128,
        ),
    ],
) -> str:
    """Get full details of a specific Azure Update by its ID (GUID from the feed)."""
    return await get_azure_update_details(update_id=update_id)


@mcp.tool()
@instrument()
async def search_azure_updates_history_tool(
    product: Annotated[str, Field(description="Filter by product name (exact match).", max_length=200)] = "",
    category: Annotated[str, Field(description="Filter by product category (exact match).", max_length=120)] = "",
    status: Annotated[str, Field(description="Filter by update status (exact match).", max_length=120)] = "",
    search: Annotated[str, Field(description="Keyword search across title and description.", max_length=200)] = "",
    from_date: Annotated[
        str, Field(description="Start date (YYYY-MM-DD). Defaults to 3 years ago.", pattern=_DATE_OR_EMPTY)
    ] = "",
    to_date: Annotated[
        str, Field(description="End date (YYYY-MM-DD). Defaults to today.", pattern=_DATE_OR_EMPTY)
    ] = "",
    max_results: Annotated[
        int, Field(description="Maximum results to return.", ge=1, le=500)
    ] = 100,
) -> str:
    """Search Azure Updates history going back up to 3 years via the OData API."""
    return await search_azure_updates_history(
        product=product or None,
        category=category or None,
        status=status or None,
        search=search or None,
        from_date=from_date or None,
        to_date=to_date or None,
        max_results=max_results,
    )


@mcp.tool()
@instrument()
async def generate_azure_updates_report_tool(
    subscription_id: SubscriptionId = "",
    report_type: Annotated[
        ReportType, Field(description="'full' (detailed) or 'executive' (summary only).")
    ] = "full",
    highlights_per_section: Annotated[
        int, Field(description="Critical updates to highlight per section.", ge=1, le=20)
    ] = 3,
    output_path: Annotated[
        str,
        Field(description="File path to save the PDF. Leave empty for auto-generated temp path.", max_length=1024),
    ] = "",
) -> str:
    """Generate a professional PDF report of Azure Updates personalised to your environment.

    Creates a colour-coded PDF with cover page, executive summary, and
    per-section detail pages showing service-grouped updates, affected
    resources, and action items.
    """
    return await generate_report(
        subscription_id=subscription_id or None,
        report_type=report_type,
        highlights_per_section=highlights_per_section,
        output_path=output_path or None,
    )


# ── Entry Point ──────────────────────────────────────────────────────


def main() -> None:
    """Start the MeghIQ MCP server."""
    parser = argparse.ArgumentParser(
        description="MeghIQ Azure Cost Optimization MCP Server",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=os.environ.get("MCP_TRANSPORT", "streamable-http"),
        help="Transport mode: stdio (local) or streamable-http (remote). Default: streamable-http",
    )
    args = parser.parse_args()

    logger.info(
        "Starting MeghIQ MCP Server (transport=%s, host=%s, port=%d)",
        args.transport, _host, _port,
    )
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
