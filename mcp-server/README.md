# MeghIQ MCP Server — Azure Cost Optimization Tools

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that exposes **23 tools** for Azure cost management, budget control, anomaly detection, utilization analysis, Azure Updates intelligence, and PDF reporting.

Built on [FastMCP](https://github.com/modelcontextprotocol/python-sdk) with streamable HTTP transport and backed entirely by Azure REST APIs.

Every tool argument is validated by a [Pydantic](https://docs.pydantic.dev/) `Annotated[..., Field(...)]` schema (regex patterns, length / numeric bounds, enums), every Azure call funnels through a single rate-limit + error sanitiser, and every invocation is instrumented with a request-id and per-tool latency counters exposed at `/metrics`.

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tools Reference](#tools-reference)
  - [Cost Query Tools](#cost-query-tools-4-tools)
  - [Forecast Tools](#forecast-tools-1-tool)
  - [Budget Tools](#budget-tools-5-tools)
  - [Alert Tools](#alert-tools-2-tools)
  - [Recommendation Tools](#recommendation-tools-2-tools)
  - [Anomaly Detection Tools](#anomaly-detection-tools-1-tool)
  - [Utilization Tools](#utilization-tools-1-tool)
  - [Azure Updates Intelligence Tools](#azure-updates-intelligence-tools-6-tools)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Running the Server](#running-the-server)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [Response Format](#response-format)
- [Azure APIs Used](#azure-apis-used)
- [Dependencies](#dependencies)
- [Testing](#testing)
- [Module Reference](#module-reference)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Client                               │
│             (Claude, Copilot, custom agent, etc.)               │
└───────────────────────────┬─────────────────────────────────────┘
                            │  Streamable HTTP / stdio
┌───────────────────────────▼─────────────────────────────────────┐
│                    server.py (FastMCP)                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  23 @mcp.tool() + @instrument() wrappers                  │   │
│  │  + Health (/ , /health) + Telemetry (/metrics)            │   │
│  └──────────────────────────────────────────────────────────┘   │
│       │           │            │            │           │       │
│  ┌────▼─────┐ ┌──▼──────┐ ┌───▼──────┐ ┌──▼──────┐ ┌──▼─────┐ │
│  │ auth.py  │ │response  │ │telemetry │ │tools/   │ │tools/  │ │
│  │ Creds    │ │ JSON fmt │ │ counters │ │http_uti │ │*.py    │ │
│  │          │ │          │ │ + req-id │ │ls (429) │ │11 mods │ │
│  └────┬─────┘ └──────────┘ └──────────┘ └─────────┘ └────────┘ │
└───────┼──────────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
┌─────────────────┐   ┌──────────────────────────────────────────┐
│ DefaultAzure    │   │          Azure REST APIs                  │
│ Credential      │   │  • Cost Management (2023-11-01)           │
│ (az login /     │   │  • Advisor (2023-01-01)                   │
│  env vars /     │   │  • Resource Graph (2022-10-01)            │
│  managed id)    │   │  • Azure Monitor (2024-02-01)             │
└─────────────────┘   │  • Azure Updates RSS Feed                 │
                      └──────────────────────────────────────────┘
```

All tools return standardised JSON via `response.py` helpers. Azure API calls use direct REST via `httpx` with bearer token authentication (except utilization metrics which use `azure-mgmt-monitor` SDK). All HTTP responses are funnelled through `tools/http_utils.check_azure_response`, which handles HTTP 429 with `Retry-After`, rejects 2xx codes outside an explicit allow-list, and sanitises upstream error bodies before they reach the client.

---

## Project Structure

```
mcp-server/
├── server.py                  # Entry point — registers 23 MCP tools, health/metrics, CLI
├── auth.py                    # Azure credential management & token acquisition
├── response.py                # Standardised JSON response helpers (success/error)
├── telemetry.py               # Request-id ContextVar, per-tool counters, @instrument decorator
├── requirements.txt           # Pinned Python dependencies (==)
├── startup.sh                 # Azure App Service startup script
├── .env                       # Environment variables (create manually)
├── tests/
│   ├── test_http_utils.py            # Unit tests for the shared HTTP helper (httpx.MockTransport)
│   ├── test_telemetry.py             # Unit tests for the telemetry decorator + counters
│   ├── test_validators.py            # Unit tests for input validators (UUID, KQL, paths, IDs)
│   ├── test_server_integration.py    # In-process spawn + /health, /metrics, MCP handshake
│   ├── test_mcp.py                   # Standalone integration script (needs Azure creds)
│   ├── test_cost.py / test_extended.py / test_verbose.py  # Live Azure smoke scripts
└── tools/
    ├── __init__.py
    ├── http_utils.py          # check_azure_response: 429 + error sanitiser (one source of truth)
    ├── validators.py          # Input validators and error-message sanitisers
    ├── cost_services.py       # Cost queries (subscription, resource group, management group, compare)
    ├── forecast.py            # Cost forecasting
    ├── budgets.py             # Budget CRUD operations
    ├── alerts.py              # Cost alert management
    ├── anomalies.py           # Anomaly detection (native API + heuristic fallback)
    ├── recommendations.py     # Azure Advisor cost recommendations
    ├── utilization.py         # Dynamic service utilization metrics
    ├── resource_discovery.py  # Azure Resource Graph discovery & token extraction
    ├── azure_updates.py            # Azure Updates RSS feed parser
    ├── azure_updates_history.py    # Historical Azure Updates via OData API (up to 3 years)
    ├── update_intelligence.py      # Two-phase personalised update digest & drill-down engine
    └── pdf_report.py               # Professional colour-coded PDF report generation
```

---

## Tools Reference

### Cost Query Tools (4 tools)

| Tool | Description |
|------|-------------|
| `query_subscription_costs_tool` | Query costs for an Azure subscription, grouped by dimensions (ServiceName, ResourceGroup, ResourceType, Tags, etc.). Supports ActualCost/AmortizedCost and multiple timeframes. |
| `query_resource_group_costs_tool` | Query costs scoped to a specific resource group. |
| `query_management_group_costs_tool` | Query costs across a management group (aggregates all child subscriptions). |
| `compare_costs_tool` | Compare costs between two custom time periods. Returns per-dimension cost change and percentage delta. |

**Common Parameters:**
- `subscription_id` — Azure subscription ID (defaults to `AZURE_SUBSCRIPTION_ID` env var)
- `query_type` — `ActualCost` or `AmortizedCost`
- `timeframe` — `MonthToDate`, `BillingMonthToDate`, `TheLastMonth`, `TheLastBillingMonth`, `WeekToDate`, or `Custom`
- `granularity` — `Daily`, `Monthly`, or `None` (totals only)
- `group_by` — Comma-separated dimensions: `ServiceName`, `ResourceGroup`, `ResourceType`, `MeterCategory`, `ResourceLocation`, `ChargeType`, `PublisherType`, `TagKey:YourTag`
- `custom_from` / `custom_to` — Date range (`YYYY-MM-DD`) when timeframe is `Custom`

### Forecast Tools (1 tool)

| Tool | Description |
|------|-------------|
| `get_cost_forecast_tool` | Get cost forecast for a subscription or resource group. Supports up to 365-day forecast with Daily/Monthly granularity. Optionally includes actual (past) cost alongside forecast data. |

**Parameters:**
- `subscription_id`, `resource_group` — Scope
- `granularity` — `Daily` or `Monthly`
- `forecast_days` — Number of days to forecast (default 30, max 365)
- `group_by` — Optional comma-separated grouping dimensions
- `include_actual` — Include actual cost alongside forecast (default `true`)

### Budget Tools (5 tools)

| Tool | Description |
|------|-------------|
| `list_budgets_tool` | List all cost budgets for a subscription or resource group. |
| `get_budget_tool` | Get details of a specific budget including utilization percentage and notification settings. |
| `create_budget_tool` | Create a new cost budget with notification thresholds. Thresholds >100 automatically use "Forecasted" type. Defaults to 12-month duration. |
| `update_budget_tool` | Update an existing budget's amount and/or notification settings. |
| `delete_budget_tool` | Delete a cost budget. |

**Key Parameters for `create_budget_tool`:**
- `budget_name` — Name for the budget
- `amount` — Budget amount in subscription currency
- `time_grain` — `Monthly`, `Quarterly`, `Annually`, or `BillingMonth`
- `notification_thresholds` — Comma-separated thresholds (e.g. `80,100,120`). Values >100 automatically use Forecasted alert type.
- `contact_emails` — Comma-separated email addresses for notifications
- `start_date` / `end_date` — Budget period (`YYYY-MM-DDT00:00:00Z`)

### Alert Tools (2 tools)

| Tool | Description |
|------|-------------|
| `list_cost_alerts_tool` | List all cost management alerts for a subscription or resource group. Returns alert type, category, status, threshold, current spend, and contact info. |
| `dismiss_alert_tool` | Dismiss a specific cost alert by its ID. |

### Recommendation Tools (2 tools)

| Tool | Description |
|------|-------------|
| `list_cost_recommendations_tool` | List Azure Advisor cost optimization recommendations sorted by estimated savings. Covers right-sizing VMs, purchasing reservations, shutting down unused resources, etc. Results include `totalEstimatedSavings` in metadata. |
| `get_recommendation_details_tool` | Get detailed information about a specific Advisor cost recommendation including extended properties and solution steps. |

### Anomaly Detection Tools (1 tool)

| Tool | Description |
|------|-------------|
| `list_anomalies_tool` | Detect cost anomalies — unusual spending spikes. Dual strategy: tries Azure's native Cost Anomaly Detection API first; falls back to statistical heuristic (2 standard deviations above 7-day rolling average) if unavailable. Returns severity (High/Medium/Low) and deviation percentage. |

**Parameters:**
- `subscription_id` — Azure subscription ID
- `days_back` — Number of days to analyze (default 30)

### Utilization Tools (1 tool)

| Tool | Description |
|------|-------------|
| `get_service_utilization_tool` | Get utilization details of an Azure service. **Fully dynamic** — no hardcoded mappings. Discovers resource types via Azure Resource Graph, then queries available metrics from Azure Monitor's metric definitions API for each resource over the past 3 days. |

**Parameters:**
- `service_name` — Azure service to query (e.g. `"Storage"`, `"Virtual Machines"`, `"SQL"`, `"Cosmos DB"`, `"AKS"`)
- `subscription_id` — Azure subscription ID

### Azure Updates Intelligence Tools (6 tools)

These tools implement a **two-phase workflow** for Azure Updates:

```
Phase 1: get_personalized_azure_updates_tool
    → Compact service-grouped executive summary
    → IDF-weighted relevance scoring against YOUR deployed resources
    → 7 priority sections (Retirements → Security → Cost → Features → Preview → Regional → Other)

Phase 2: drill_down_azure_updates_tool
    → Expand any section, service, or status with AND filters
    → Full details for the slice you care about
```

| Tool | Description |
|------|-------------|
| `get_personalized_azure_updates_tool` | **Phase 1** — Generates a personalised Azure Updates digest. Discovers your deployed resources via Resource Graph, fetches the RSS feed, scores each update using IDF-weighted token overlap, classifies into 7 priority sections, and returns a compact service-grouped executive summary with optional CSV export. |
| `drill_down_azure_updates_tool` | **Phase 2** — Drill down into specific slice of the digest. Filters by section, service, and/or status (case-insensitive partial match, AND logic). Returns full details for matching updates above a min relevance threshold. |
| `list_all_azure_updates_tool` | List all Azure Updates from the official RSS feed (unfiltered by environment). Supports filtering by category, status, and keyword search. Limited to ~200 most recent items (~4 months). |
| `search_azure_updates_history_tool` | **Historical search** — Queries the Microsoft Release Communications OData API with server-side filtering and pagination to retrieve Azure Updates going back **up to 3 years**. Supports filtering by product, category, status, keyword search, and date range. Returns up to 500 results. |
| `get_azure_update_details_tool` | Get full details of a specific Azure Update by its GUID. |
| `generate_azure_updates_report_tool` | Generate a professional colour-coded PDF report of Azure Updates personalised to your environment. Includes cover page, executive summary, and per-section detail pages with affected resources. Supports `"full"` and `"executive"` report types. |

**Scoring Pipeline (Phase 1):**

1. Discover deployed resources via Azure Resource Graph
2. Fetch and parse all updates from the Azure Updates RSS feed
3. Compute IDF weights across all update tokens
4. Score each update against each deployed resource type (IDF-weighted set-overlap, 0.0–1.0)
5. Compute priority = relevance × (1 − urgency_weight) + urgency × urgency_weight
6. Classify into 7 sections, group by service, generate executive summary

**Parameters for `search_azure_updates_history_tool`:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `product` | string | Filter by product (exact match). Examples: `Virtual Machines`, `Azure Kubernetes Service (AKS)`, `Azure SQL Database`, `Azure Cosmos DB`, `Azure Functions` |
| `category` | string | Filter by product category (exact match). Examples: `Compute`, `Databases`, `Networking`, `Security`, `AI + machine learning`, `Storage` |
| `status` | string | Filter by status. Examples: `Launched`, `In preview`, `Retirement`, `In development` |
| `search` | string | Keyword search across title and description (case-insensitive) |
| `from_date` | string | Start date (`YYYY-MM-DD`). Defaults to 3 years ago |
| `to_date` | string | End date (`YYYY-MM-DD`). Defaults to today |
| `max_results` | int | Maximum results (default 100, max 500) |

**Priority Sections:**

| Priority | Section |
|----------|---------|
| 1 (highest) | Action Required: Retirements & Deprecations |
| 2 | Security & Compliance Updates |
| 3 | Cost & Pricing Updates |
| 4 | New Features & GA Announcements |
| 5 | Preview & Upcoming Features |
| 6 | Regional Expansion |
| 99 (lowest) | Other Updates |

---

## Prerequisites

- **Python 3.10+**
- **Azure CLI** — logged in with `az login` (or other credential type supported by `DefaultAzureCredential`)
- **RBAC Roles** on the target subscription:
  - `Cost Management Reader` — for cost queries, forecasts, budgets, alerts, anomalies
  - `Reader` — for Resource Graph, Azure Monitor, and Advisor recommendations

---

## Setup

```bash
# Navigate to the MCP server directory
cd mcp-server

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in the `mcp-server/` directory:

```env
AZURE_SUBSCRIPTION_ID=your-subscription-id-here
```

---

## Running the Server

```bash
# Ensure Azure CLI is logged in
az login

# Run the MCP server (Streamable HTTP on port 8000, default)
python server.py

# Or specify transport mode explicitly
python server.py --transport streamable-http   # HTTP mode (default)
python server.py --transport stdio             # stdio mode (for local MCP clients)
```

The server starts on `http://localhost:8000` using the Streamable HTTP transport by default.

**MCP endpoint:** `http://localhost:8000/mcp`

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_SUBSCRIPTION_ID` | **Yes** | — | Target Azure subscription ID |
| `MCP_HOST` | No | `0.0.0.0` | Host address to bind |
| `MCP_SERVER_PORT` | No | `8000` | Port to listen on |
| `MCP_TRANSPORT` | No | `streamable-http` | Transport mode (`streamable-http` or `stdio`) |
| `MEGHIQ_LOG_LEVEL` | No | `WARNING` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Every log record carries a `[req=<id>]` correlation tag generated by `telemetry.instrument`. |
| `MEGHIQ_METRICS_TOKEN` | No | _(unset)_ | If non-empty, requires `Authorization: Bearer <token>` on `/metrics`. When unset the endpoint is open and the server logs a startup `WARNING`. |

For service principal authentication (instead of `az login`), set:
- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_SECRET`

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root health check → `{"status": "ok", "service": "meghiq-mcp"}` |
| `/health` | GET | Health check → `{"status": "ok", "service": "meghiq-mcp"}` |
| `/metrics` | GET | In-memory telemetry snapshot. Returns JSON by default; returns the Prometheus exposition format when the request sends `Accept: text/plain`. Optional bearer-token auth via `MEGHIQ_METRICS_TOKEN` (off by default — the server logs a startup WARNING so the open state is impossible to deploy by accident). |
| `/mcp` | POST | MCP protocol endpoint (streamable HTTP transport) |

**`/metrics` response shape (JSON, default):**

```json
{
  "totals": {
    "tool_calls_total": 42,
    "tool_errors_total": 1,
    "unique_tools": 5
  },
  "tools": {
    "query_subscription_costs_tool": {
      "calls": 12,
      "errors": 0,
      "avg_latency_ms": 612.3,
      "max_latency_ms": 1840.0
    }
  }
}
```

**`/metrics` Prometheus format (when `Accept: text/plain`):**

```text
# HELP meghiq_tool_calls_total Total successful + failed invocations per tool.
# TYPE meghiq_tool_calls_total counter
meghiq_tool_calls_total{tool="query_subscription_costs_tool"} 12
# HELP meghiq_tool_errors_total Invocations that returned an error envelope or raised.
# TYPE meghiq_tool_errors_total counter
meghiq_tool_errors_total{tool="query_subscription_costs_tool"} 0
# HELP meghiq_tool_latency_ms_avg Average wall-clock latency per tool in milliseconds.
# TYPE meghiq_tool_latency_ms_avg gauge
meghiq_tool_latency_ms_avg{tool="query_subscription_costs_tool"} 612.3
# HELP meghiq_tool_latency_ms_max Peak wall-clock latency per tool in milliseconds.
# TYPE meghiq_tool_latency_ms_max gauge
meghiq_tool_latency_ms_max{tool="query_subscription_costs_tool"} 1840.0
```

**Auth.** Set `MEGHIQ_METRICS_TOKEN` to a non-empty value and every `/metrics` request must carry `Authorization: Bearer <token>`. The comparison uses `hmac.compare_digest`, so it is constant-time and safe against timing oracles. Unauthorised requests get a uniform `401 unauthorized` body (no hint about whether the header was missing or the token wrong).

---

## Response Format

All tools return standardised JSON:

**Success:**
```json
{
  "status": "success",
  "data": [ ... ],
  "metadata": {
    "timestamp": "2025-01-15T10:30:00+00:00",
    "scope": "subscriptions/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "timeframe": "MonthToDate",
    "currency": "USD",
    "rowCount": 15
  }
}
```

**Error:**
```json
{
  "status": "error",
  "error": {
    "message": "Azure API error 401: ...",
    "code": "401"
  },
  "metadata": {
    "timestamp": "2025-01-15T10:30:00+00:00"
  }
}
```

---

## Azure APIs Used

| API | Version | Used By |
|-----|---------|---------|
| Azure Cost Management Query | `2023-11-01` | cost_services, forecast, anomalies |
| Azure Cost Management Budgets | `2023-11-01` | budgets |
| Azure Cost Management Alerts | `2023-11-01` | alerts |
| Azure Cost Anomaly Detection | `2023-11-01` | anomalies (primary) |
| Azure Advisor | `2023-01-01` | recommendations |
| Azure Resource Graph | `2022-10-01` | resource_discovery, utilization |
| Azure Monitor Metrics | `2024-02-01` | utilization |
| Azure Monitor Metric Definitions | `2024-02-01` | utilization |
| Azure Updates RSS Feed | — | azure_updates, update_intelligence |
| Microsoft Release Communications OData API | v2 | azure_updates_history |

---

## Dependencies

All versions are **pinned with `==`** in [`requirements.txt`](requirements.txt) for reproducible builds. Run `pip freeze > requirements.lock` to capture the full transitive graph for auditing.

| Package | Pinned version | Purpose |
|---------|---------------|---------|
| `mcp[cli]` | `1.23.0` | FastMCP framework and transport |
| `pydantic` | `2.13.4` | Tool-argument validation (`Annotated`/`Field`) and JSON Schema generation |
| `azure-identity` | `1.25.3` | `DefaultAzureCredential` for authentication |
| `azure-mgmt-costmanagement` | `4.0.1` | Azure Cost Management SDK client |
| `azure-mgmt-monitor` | `6.0.2` | Azure Monitor metrics SDK (utilization) |
| `azure-mgmt-resource` | `23.4.0` | Resource management client |
| `azure-mgmt-resourcegraph` | `8.0.0` | Resource Graph client (resource discovery) |
| `httpx` | `0.28.1` | Async HTTP client for Azure REST APIs |
| `python-dotenv` | `1.2.2` | `.env` file loading |
| `python-dateutil` | `2.9.0.post0` | Date calculations (budget defaults) |
| `fpdf2` | `2.8.4` | PDF report generation |
| `starlette` | `1.0.1` | Health / metrics routes |
| `uvicorn` | `0.34.0` | ASGI server |
| `defusedxml` | `0.7.1` | XXE-safe XML parsing for the Azure Updates RSS feed |

---

## Testing

The test suite is split into three tiers; the first two run in CI and need **no** Azure credentials.

### 1. Unit tests (fastest, hermetic)

```bash
cd mcp-server
pip install pytest pytest-asyncio
python -m pytest tests/test_http_utils.py tests/test_telemetry.py tests/test_validators.py -v
```

Covers the rate-limit/error sanitiser, the telemetry decorator (request-id ContextVar, per-tool counters, error envelope detection, signature pre-resolution for FastMCP), and every input validator (UUID, resource group, KQL sanitiser, Azure resource ID, output-path traversal). Uses `httpx.MockTransport` and `tmp_path` fixtures — no network, no Azure.

### 2. Server integration tests (in-process)

```bash
python -m pytest tests/test_server_integration.py -v
```

Spawns `server.py` on an ephemeral port, then verifies `GET /health`, `GET /metrics` (JSON shape, Prometheus exposition format, and bearer-token auth gating), the full MCP `initialize` → `notifications/initialized` → `tools/list` handshake (asserts ≥23 tools register with valid JSON Schema), and calls `list_all_azure_updates_tool` (public RSS feed). The metrics endpoint is re-queried afterwards to confirm the call counter incremented.

### 3. Live Azure smoke scripts (need credentials)

These are standalone scripts (not pytest) — run them manually with `az login` active and `AZURE_SUBSCRIPTION_ID` exported:

```bash
# Start the server in another terminal first
python server.py

# Then in this terminal
python tests/test_mcp.py        # MCP handshake + Cost Management call
python tests/test_cost.py       # Direct Cost Management SDK call (with retry)
python tests/test_extended.py   # Extended workflow against multiple tools
python tests/test_verbose.py    # Same, with verbose logging
```

### Continuous integration

GitHub Actions workflow at [`.github/workflows/mcp-server-ci.yml`](../.github/workflows/mcp-server-ci.yml) runs on every push / PR touching `mcp-server/**`:

1. `py_compile` over every tracked `.py`
2. Server import + tool-registration assertion (≥23 tools)
3. Unit tests (`test_http_utils.py`, `test_telemetry.py`, `test_validators.py`)
4. Server integration tests (`test_server_integration.py`)
5. `bandit -ll` static security scan (fails on HIGH severity)
6. `pip-audit --strict` dependency vulnerability scan

---

## Module Reference

### `server.py`

Main entry point. Registers all 23 MCP tools as `@mcp.tool()` + `@instrument()` wrappers using reusable Pydantic `Annotated[..., Field(...)]` aliases (`SubscriptionId`, `ResourceGroupOpt`, `QueryType`, `Timeframe`, …) so the MCP client receives precise JSON Schemas (regex patterns, bounds, enums, examples) for every argument. Configures Starlette routes for `/`, `/health`, and `/metrics`, attaches the request-id logging filter, and provides a CLI with `--transport` flag.

### `telemetry.py`

Lightweight in-process observability with no external dependency:

- `RequestContextFilter` — injects `record.request_id` (a 12-char `uuid4` hex slice) into every log record so concurrent tool calls are correlated.
- `instrument(tool_name=None)` — async decorator that allocates a request id, times the call with `time.perf_counter`, detects `{"status": "error"}` envelopes returned by `response.error_response`, increments per-tool counters under a `threading.Lock`, and emits a single `INFO` log line. Pre-resolves the wrapped function's type hints onto `wrapper.__signature__` so FastMCP's schema introspection can see them without needing access to the caller's module globals.
- `telemetry_snapshot()` — returns the JSON dict surfaced by the `/metrics` route.

### `tools/http_utils.py`

One source of truth for Azure HTTP error handling:

- `handle_rate_limit(resp)` — returns a sanitised `TooManyRequests` envelope honouring `Retry-After` (defaults to 60 s) for HTTP 429, otherwise `None`.
- `handle_azure_error(resp, api_label)` — logs the raw body server-side (capped at 500 chars) and returns a sanitised error envelope; never leaks upstream content to the MCP client.
- `check_azure_response(resp, api_label, allow_statuses=(200,))` — one-shot wrapper. Strictly enforces `allow_statuses`: a 2xx response outside the allow set (e.g. an unexpected 201) is reported as an error so callers can't silently mishandle it.

### `auth.py`

Azure credential management. Provides:
- `get_credential()` — Cached `DefaultAzureCredential` singleton
- `get_subscription_id()` — Reads `AZURE_SUBSCRIPTION_ID` from environment
- `get_token(scope)` — Acquires bearer token for Azure Management plane
- `get_cost_management_client()` — Azure Cost Management SDK client
- `get_resource_graph_client()` — Azure Resource Graph SDK client
- `get_monitor_client(sub_id)` — Azure Monitor SDK client
- `get_resource_client(sub_id)` — Azure Resource Management SDK client

Supports three credential sources: `az login`, environment variables (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`), and Managed Identity.

### `response.py`

Standardised JSON response helpers used by all tools:
- `success_response(data, scope=, timeframe=, currency=, extra_meta=)` — Wraps data with metadata (timestamp, rowCount for lists)
- `error_response(message, code=)` — Wraps error message with timestamp

### `tools/cost_services.py`

Cost query engine. Builds Cost Management Query API payloads, executes against subscription/resource-group/management-group scopes, parses table responses, handles 429 rate limiting. The `compare_costs` function queries two periods independently and merges results with per-dimension cost change and percentage delta.

### `tools/forecast.py`

Cost forecasting via the Cost Management Forecast API. Supports configurable forecast horizon (up to 365 days), granularity, and dimension grouping. Can include actual historical cost alongside forecast data.

### `tools/budgets.py`

Full CRUD for Azure cost budgets. Automatically calculates 12-month default end dates using `python-dateutil`. Notification thresholds >100 automatically use "Forecasted" alert type, ≤100 use "Actual". Parses budget utilization percentage from current spend vs amount.

### `tools/alerts.py`

Cost alert management. Lists alerts with type, category, status, threshold, current spend, and contact emails. Supports dismissing alerts via PATCH with `status=Dismissed`.

### `tools/anomalies.py`

Dual-strategy anomaly detection:
1. **Native API** — Tries Azure Cost Anomaly Detection API first
2. **Heuristic fallback** — If native API unavailable (404/400/501), queries daily costs and flags days where spending exceeds 2 standard deviations above a 7-day rolling average. Returns severity (High >100%, Medium >50%, Low) and deviation percentage.

### `tools/recommendations.py`

Azure Advisor cost optimization recommendations. Fetches recommendations filtered by `Category eq 'Cost'`, handles pagination via `nextLink`, extracts estimated savings, and sorts results by savings descending. Includes `totalEstimatedSavings` in metadata.

### `tools/utilization.py`

Dynamic service utilization metrics. No hardcoded resource/metric mappings:
1. Discovers resources of the requested service type via Azure Resource Graph
2. Queries Azure Monitor's metric definitions API for each resource to find available metrics
3. Fetches metric values (average aggregation) over the past 3 days
4. Returns per-resource utilization breakdown

### `tools/resource_discovery.py`

Azure Resource Graph-based resource discovery with intelligent token extraction:
- Queries all resources in a subscription via Resource Graph API
- Summarises by type, count, and location
- Extracts semantic tokens from ARM resource type strings (camelCase splitting, compound pair generation, noise word removal)
- Tokens are used by `update_intelligence.py` for relevance scoring

### `tools/azure_updates.py`

Azure Updates RSS feed parser (XML-based, no `feedparser` dependency). Limited to ~200 most recent items (~4 months):
- Fetches from `https://www.microsoft.com/releasecommunications/api/v2/azure/rss`
- Parses XML items extracting id, title, status (from bracket prefix), categories (service vs meta), description, links
- Supports filtering by category, status, and keyword search
- Generates internal tokens (`_category_tokens`, `_meta_tokens`, `_title_tokens`) for matching

### `tools/azure_updates_history.py`

Historical Azure Updates search via the Microsoft Release Communications OData REST API:
- **Full API endpoint:** `https://www.microsoft.com/releasecommunications/api/v2/azure`
- Returns structured JSON (not RSS/XML) with OData `$top`, `$skip`, `$count`, `$filter` support
- Server-side filtering on `products`, `productCategories`, and `status`/`tags` fields
- Tag-aware status filtering: retirement items are stored in `tags` (not `status`); the tool handles both transparently
- Client-side keyword search across title and description
- Date range filtering with configurable `from_date`/`to_date` (max 3 years lookback)
- Paginated fetching (100 items/page, up to 50 pages) with date-sorted results (newest first)
- Returns up to 500 results per query
- Products use exact names from the API taxonomy (e.g. `Virtual Machines`, `Azure Kubernetes Service (AKS)`, `Azure SQL Database`)

### `tools/update_intelligence.py`

Core intelligence engine implementing the two-phase personalised updates workflow:
- **Phase 1 (`get_personalized_updates`):** Discovers deployed resources → fetches RSS feed → computes IDF token weights → scores each update via IDF-weighted set-overlap → classifies into 7 priority sections → groups by service → generates compact executive summary with optional CSV export (16 columns)
- **Phase 2 (`drill_down_updates`):** Accepts section/service/status filters (case-insensitive partial match, AND logic) → returns full details for matching updates above a min relevance threshold
- Scoring: `priority = relevance × (1 − urgency_weight) + urgency × urgency_weight`
- Impact assessment identifies which deployed resource types are affected per update

### `tools/pdf_report.py`

Professional colour-coded PDF report generator using `fpdf2`:
- **Cover page** — Subscription summary, top services, generation timestamp
- **Executive summary** — Key metrics, section overview with colour coding
- **Top Priority Updates** — Critical highlights across all sections
- **Per-section detail pages** — Critical highlights + service group summaries (full report only)
- Colour palette: Red (Retirements), Orange (Security), Green (Cost), Blue (Features), Purple (Preview), Teal (Regional), Grey (Other)
- Handles Unicode→Latin-1 text sanitisation
- Output defaults to temp directory with timestamped filename

## Azure Deployment

The MCP server is deployed to **Azure App Service** (Linux, Python 3.11) in **Central India**.

### Deployed Infrastructure

| Resource | Name | Region |
|----------|------|--------|
| Resource Group | `meghiq-mcp-rg` | Central India |
| App Service Plan | `meghiq-mcp-plan` (B1 Linux) | Central India |
| Web App | `meghiq-mcp-server` (Python 3.11) | Central India |

### Live Endpoints

| Endpoint | URL |
|----------|-----|
| Health Check | `https://meghiq-mcp-server.azurewebsites.net/health` |
| MCP Protocol | `https://meghiq-mcp-server.azurewebsites.net/mcp` |

### Security

- **System-assigned Managed Identity** — used for Azure API authentication (no secrets stored)
- **RBAC Roles** assigned on subscription:
  - `Cost Management Reader`
  - `Reader`

### App Settings

| Setting | Value |
|---------|-------|
| `AZURE_SUBSCRIPTION_ID` | Target subscription |
| `MCP_TRANSPORT` | `streamable-http` |
| `MCP_HOST` | `0.0.0.0` |
| `MCP_SERVER_PORT` | `8000` |
| `WEBSITES_PORT` | `8000` |
| `WEBSITES_CONTAINER_START_TIME_LIMIT` | `300` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |
| `MEGHIQ_LOG_LEVEL` | `INFO` |

### Redeploying

```powershell
# From the mcp-server/ directory
cd mcp-server

# Create deployment zip (exclude venv, pycache, env files)
$exclude = @('.venv', '__pycache__', '.env', '*.pyc', 'test_*.py')
$items = Get-ChildItem -Path . -Exclude $exclude
Compress-Archive -Path $items -DestinationPath $env:TEMP\meghiq-mcp-deploy.zip -Force

# Deploy
az webapp deploy --name meghiq-mcp-server --resource-group meghiq-mcp-rg `
  --src-path "$env:TEMP\meghiq-mcp-deploy.zip" --type zip
```

---

## Testing with MCP Inspector

```bash
# Use the MCP CLI inspector to test tools interactively
mcp dev server.py
```

## Connecting from Agent Framework

```python
from agent_framework import MCPStreamableHTTPTool

# Local development
mcp_tool = MCPStreamableHTTPTool(
    name="MeghIQ Cost Optimizer",
    url="http://localhost:8000/mcp",
)

# Azure deployment
mcp_tool = MCPStreamableHTTPTool(
    name="MeghIQ Cost Optimizer",
    url="https://meghiq-mcp-server.azurewebsites.net/mcp",
)
```

---

## Sample Questions

Once connected to an MCP client (Copilot, Claude, custom agent, etc.), try these prompts:

### Cost Analysis
- "What are my top 5 most expensive Azure services this month?"
- "Show me a daily cost breakdown for the last 7 days grouped by resource group."
- "Compare my Azure spending between last month and this month — what changed?"
- "How much am I spending on storage vs compute services month-to-date?"
- "What are the costs for the `meghiq-mcp-rg` resource group this billing period?"

### Forecasting
- "Forecast my Azure costs for the next 30 days."
- "What will my spending look like for the next quarter, broken down by service?"

### Budgets
- "List all my Azure budgets and how much of each has been used."
- "Create a monthly budget of $5,000 with alerts at 80% and 100%."
- "Update my 'production-budget' to $8,000 and add a 120% forecasted alert."
- "Delete the 'test-budget' budget."

### Alerts & Anomalies
- "Are there any active cost alerts I should know about?"
- "Have there been any unusual spending spikes in the last 30 days?"
- "Show me cost anomalies for my subscription over the past 2 weeks."

### Recommendations
- "What cost optimization recommendations does Azure Advisor have for me?"
- "Give me details on the top recommendation — how much can I save?"

### Utilization
- "What is the current utilization of my Virtual Machines?"
- "Show me utilization metrics for my SQL databases."
- "How are my Storage accounts being utilized?"

### Azure Updates
- "What Azure updates are relevant to my environment?"
- "Drill down into the retirement and deprecation updates for my services."
- "Are there any security updates that affect the services I'm using?"
- "Show me all Azure updates related to Azure Kubernetes Service."
- "Generate a PDF report of Azure updates personalized to my subscription."

### Historical Azure Updates (up to 3 years)
- "Find all Virtual Machine updates from the last 2 years."
- "Show me all Azure SQL Database retirements in the past 3 years."
- "Search for updates mentioning 'confidential' across all Azure services since 2024."
- "What AKS updates were launched between January 2025 and March 2026?"
- "List all Compute category updates that are in preview right now."
- "Find any retirement notices for Azure Functions in the last year."

### Combined Cost Optimization (agent orchestrates multiple tools)
- "Give me cost recommendations based on my current utilization and Azure updates for the last 2 years for the top 5 costly resource."
- "Which of my resources are idle or underutilized, and how much would I save by removing them?"
- "Are any of my services being retired? What cheaper alternatives are available?"
- "Compare my current VM sizes against the latest Azure VM series — can I right-size or upgrade to save money?"
- "Show me orphaned resources (disks, IPs, extensions) across all my resource groups and the monthly cost impact."
- "What reserved instance or savings plan opportunities exist based on my last 3 months of spending?"
- "Are there any cost anomalies this month, and what resources caused the spike?"
- "Which resource groups have the highest cost growth month-over-month, and are those resources actually being used?"
- "Give me a full cost optimization summary: top spending services, Advisor recommendations, underutilized resources, and upcoming retirements."
- "What serverless or consumption-based alternatives exist for my always-on VMs and App Services?"
