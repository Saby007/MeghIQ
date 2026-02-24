# Azure Cost Management MCP Server

A Model Context Protocol (MCP) server that provides structured JSON access to Azure Cost Management data — costs, forecasts, budgets, alerts, optimization recommendations, and anomaly detection.

## Features

| Category | Tools | Description |
|----------|-------|-------------|
| **Cost Queries** | `query_subscription_costs` | Query costs by subscription with groupBy (ServiceName, ResourceGroup, ResourceType, Tags) |
| | `query_resource_group_costs` | Query costs scoped to a resource group |
| | `query_management_group_costs` | Query costs across a management group |
| | `compare_costs` | Compare costs between two custom time periods |
| **Forecasts** | `get_cost_forecast` | Daily/monthly cost forecasts with configurable horizon |
| **Budgets** | `list_budgets` | List all budgets with utilization % |
| | `get_budget` | Get budget details |
| | `create_budget` | Create budget with notification thresholds |
| | `update_budget` | Update budget amount/notifications |
| | `delete_budget` | Delete a budget |
| **Alerts** | `list_cost_alerts` | List cost management alerts |
| | `dismiss_alert` | Dismiss a specific alert |
| **Recommendations** | `list_cost_recommendations` | Azure Advisor cost recommendations sorted by savings |
| | `get_recommendation_details` | Detailed info on a specific recommendation |
| **Anomaly Detection** | `list_anomalies` | Detect unusual spending spikes |

All tools return **structured JSON** with `status`, `data`, and `metadata` fields.

## Prerequisites

- Python 3.10+
- Azure CLI installed and authenticated (`az login`)
- Azure subscription with Cost Management Reader (or Contributor) role
- (For recommendations) Azure Advisor access

## Installation

### Option 1: Install from source (recommended for development)

```bash
cd CostManagement
pip install -e .
```

### Option 2: Install with uv

```bash
uv pip install -e .
```

### Option 3: Run directly without installing

```bash
python -m azure_cost_mcp
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_SUBSCRIPTION_ID` | Yes | Default Azure subscription ID |
| `AZURE_COST_MCP_LOG_LEVEL` | No | Logging level: DEBUG, INFO, WARNING (default), ERROR |

Authentication uses `DefaultAzureCredential` which picks up credentials from:
1. `az login` (Azure CLI) — recommended for local dev
2. Environment variables (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`)
3. Managed Identity (when running in Azure)

### VS Code (GitHub Copilot Agent Mode)

The `.vscode/mcp.json` is already configured. Just:

1. Install the project: `pip install -e .`
2. Sign in to Azure: `az login`
3. Open Copilot in Agent mode and click refresh on the tools list
4. Ask: *"What are my top spending Azure services this month?"*

### Claude Desktop

Copy `claude_desktop_config.json` to your Claude Desktop config directory:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Update `AZURE_SUBSCRIPTION_ID` with your actual subscription ID.

### Other MCP Clients

Add to your MCP client config:

```json
{
  "mcpServers": {
    "azure-cost-management": {
      "command": "python",
      "args": ["-m", "azure_cost_mcp"],
      "env": {
        "AZURE_SUBSCRIPTION_ID": "your-subscription-id"
      }
    }
  }
}
```

## Usage Examples

### Natural Language Queries (via AI agent)

- *"What are my Azure costs this month by service?"*
- *"Show me costs for the 'production' resource group for the last 3 months"*
- *"Compare my December and January Azure spending"*
- *"What's my cost forecast for the next 30 days?"*
- *"List all my budgets and show utilization"*
- *"Are there any cost alerts I should be aware of?"*
- *"What cost optimization recommendations does Azure Advisor have?"*
- *"Have there been any unusual spending spikes in the last month?"*

### Direct Tool Calls (MCP protocol)

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "query_subscription_costs_tool",
    "arguments": {
      "timeframe": "MonthToDate",
      "granularity": "Daily",
      "group_by": "ServiceName"
    }
  }
}
```

### Example JSON Output

```json
{
  "status": "success",
  "data": [
    {
      "Cost": 1234.56,
      "CostUSD": 1234.56,
      "UsageDate": 20260218,
      "ServiceName": "Virtual Machines"
    },
    {
      "Cost": 567.89,
      "CostUSD": 567.89,
      "UsageDate": 20260218,
      "ServiceName": "Storage"
    }
  ],
  "metadata": {
    "timestamp": "2026-02-19T10:30:00+00:00",
    "scope": "subscriptions/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "timeframe": "MonthToDate",
    "currency": "USD",
    "rowCount": 2
  }
}
```

## Architecture

```
src/azure_cost_mcp/
├── __init__.py          # Package metadata
├── __main__.py          # python -m entry point
├── server.py            # FastMCP server — registers all tools
├── auth.py              # Azure authentication (DefaultAzureCredential)
├── response.py          # JSON response formatting helpers
└── tools/
    ├── __init__.py
    ├── cost_query.py    # Cost queries (Query API)
    ├── forecast.py      # Cost forecasts (Forecast API)
    ├── budgets.py       # Budget CRUD (Budgets API)
    ├── alerts.py        # Cost alerts (Alerts API)
    ├── recommendations.py  # Advisor cost recommendations
    └── anomalies.py     # Anomaly detection (native + heuristic fallback)
```

## Azure APIs Used

| API | Docs |
|-----|------|
| Cost Management Query | [learn.microsoft.com](https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage) |
| Cost Management Forecast | [learn.microsoft.com](https://learn.microsoft.com/en-us/rest/api/cost-management/forecast/usage) |
| Cost Management Budgets | [learn.microsoft.com](https://learn.microsoft.com/en-us/rest/api/cost-management/budgets) |
| Cost Management Alerts | [learn.microsoft.com](https://learn.microsoft.com/en-us/rest/api/cost-management/alerts) |
| Azure Advisor | [learn.microsoft.com](https://learn.microsoft.com/en-us/rest/api/advisor/recommendations) |

## Comparison with AWS MCP Server

| Feature | AWS MCP | This Server |
|---------|---------|-------------|
| Cost queries | Cost Explorer API | Cost Management Query API |
| Forecasts | Cost Explorer | Cost Management Forecast API |
| Budgets | AWS Budgets | Cost Management Budgets API |
| Anomaly detection | Cost Anomaly Detection | Native API + heuristic fallback |
| Recommendations | Cost Optimization Hub, Compute Optimizer | Azure Advisor (Cost category) |
| Storage analysis | S3 Storage Lens | *(not yet — planned)* |
| Output format | Natural language | Structured JSON |
