# Azure Cost Management MCP Server

A Model Context Protocol (MCP) server that provides structured JSON access to Azure Cost Management data and personalised Azure Updates Intelligence — costs, forecasts, budgets, alerts, optimization recommendations, anomaly detection, environment-aware update digests, and PDF reports.

## Features

### Cost Management Tools

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

### Azure Updates Intelligence Tools

| Category | Tools | Description |
|----------|-------|-------------|
| **Personalised Updates** | `get_personalized_azure_updates` | Environment-aware digest — discovers your deployed resources, fetches Azure Updates RSS, scores relevance using IDF-weighted token matching, and classifies into priority sections |
| **Browse Updates** | `list_all_azure_updates` | List/filter all Azure Updates from the official RSS feed (unfiltered by environment) |
| | `get_azure_update_details` | Get full details of a specific update by ID |
| **PDF Reports** | `generate_azure_updates_report` | Generate a professional colour-coded PDF report with cover page, executive summary, and per-section details |

All tools return **structured JSON** with `status`, `data`, and `metadata` fields.

## Prerequisites

- Python 3.10+
- Azure CLI installed and authenticated (`az login`)
- Azure subscription with Cost Management Reader (or Contributor) role
- (For recommendations) Azure Advisor access
- (For PDF reports) `fpdf2` — installed automatically from dependencies

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

## Transport Modes

The server supports two transport modes:

### stdio (default) — Local MCP clients

```bash
azure-cost-mcp                        # or: python -m azure_cost_mcp
azure-cost-mcp --transport stdio      # explicit
```

Used by Claude Desktop, VS Code Copilot, and other local MCP clients.

### Streamable HTTP — Remote access

```bash
azure-cost-mcp --transport streamable-http
```

Starts an HTTP server at `http://0.0.0.0:8000/mcp`. Clients connect using the URL directly — no process spawning needed.

Configure host/port via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HOST` | `0.0.0.0` | Bind address |
| `MCP_PORT` | `8000` | Listen port |
| `MCP_TRANSPORT` | `stdio` | Default transport (overridden by `--transport` flag) |

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_SUBSCRIPTION_ID` | Yes | Default Azure subscription ID |
| `AZURE_COST_MCP_LOG_LEVEL` | No | Logging level: DEBUG, INFO, WARNING (default), ERROR |
| `MCP_TRANSPORT` | No | Transport mode: `stdio` or `streamable-http` |
| `MCP_HOST` | No | HTTP bind address (default: `0.0.0.0`) |
| `MCP_PORT` | No | HTTP listen port (default: `8000`) |

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

### Claude Desktop — Local (stdio)

Copy `claude_desktop_config.json` to your Claude Desktop config directory:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Update `AZURE_SUBSCRIPTION_ID` with your actual subscription ID.

### Claude Desktop — Remote (Streamable HTTP)

If the server is deployed to Azure App Service (or any host), point your client directly at the URL:

```json
{
  "mcpServers": {
    "azure-cost-management": {
      "url": "https://your-app.azurewebsites.net/mcp"
    }
  }
}
```

### Other MCP Clients — Local

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

## Deployment

### Docker

Build and run locally:

```bash
docker build -t azure-cost-mcp .
docker run -p 8000:8000 \
  -e AZURE_SUBSCRIPTION_ID=your-sub-id \
  -e AZURE_CLIENT_ID=... \
  -e AZURE_TENANT_ID=... \
  -e AZURE_CLIENT_SECRET=... \
  azure-cost-mcp
```

### Azure App Service (Container)

1. Create an Azure Container Registry and build the image:

```bash
az acr create --name myacr --resource-group myRG --sku Basic --admin-enabled true
az acr build --registry myacr --resource-group myRG --image azure-cost-mcp:latest .
```

2. Create an App Service and deploy:

```bash
az appservice plan create --name myPlan --resource-group myRG --is-linux --sku B1
az webapp create --name my-mcp-server --resource-group myRG --plan myPlan \
  --container-image-name myacr.azurecr.io/azure-cost-mcp:latest \
  --container-registry-url https://myacr.azurecr.io \
  --container-registry-user myacr \
  --container-registry-password <password>
```

3. Configure environment and managed identity:

```bash
az webapp config appsettings set --name my-mcp-server --resource-group myRG \
  --settings WEBSITES_PORT=8000 AZURE_SUBSCRIPTION_ID=your-sub-id
az webapp identity assign --name my-mcp-server --resource-group myRG
```

4. Grant RBAC roles to the managed identity:

```bash
az role assignment create --assignee <principalId> --role "Reader" --scope /subscriptions/<sub-id>
az role assignment create --assignee <principalId> --role "Cost Management Reader" --scope /subscriptions/<sub-id>
```

The server will be available at `https://my-mcp-server.azurewebsites.net/mcp`.

## Usage Examples

### Natural Language Queries (via AI agent)

**Cost Management:**
- *"What are my Azure costs this month by service?"*
- *"Show me costs for the 'production' resource group for the last 3 months"*
- *"Compare my December and January Azure spending"*
- *"What's my cost forecast for the next 30 days?"*
- *"List all my budgets and show utilization"*
- *"Are there any cost alerts I should be aware of?"*
- *"What cost optimization recommendations does Azure Advisor have?"*
- *"Have there been any unusual spending spikes in the last month?"*

**Azure Updates Intelligence:**
- *"What Azure updates are relevant to my environment?"*
- *"Are there any upcoming retirements that affect my deployed resources?"*
- *"Show me security updates for services I'm using"*
- *"Generate a PDF report of Azure updates for my subscription"*
- *"List all Azure updates about Kubernetes"*

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
├── __init__.py              # Package metadata
├── __main__.py              # python -m entry point
├── server.py                # FastMCP server — registers all tools, supports stdio + streamable-http
├── auth.py                  # Azure authentication (DefaultAzureCredential)
├── response.py              # JSON response formatting helpers
└── tools/
    ├── __init__.py
    ├── cost_query.py        # Cost queries (Query API)
    ├── forecast.py          # Cost forecasts (Forecast API)
    ├── budgets.py           # Budget CRUD (Budgets API)
    ├── alerts.py            # Cost alerts (Alerts API)
    ├── recommendations.py   # Advisor cost recommendations
    ├── anomalies.py         # Anomaly detection (native + heuristic fallback)
    ├── resource_discovery.py  # Azure Resource Graph — deployed resource inventory & token extraction
    ├── azure_updates.py     # Azure Updates RSS feed parser with dynamic tokenisation
    ├── update_intelligence.py # Relevance scoring, IDF weighting, section classification
    └── pdf_report.py        # Professional PDF report generation (fpdf2)
```

## Azure APIs Used

| API | Docs |
|-----|------|
| Cost Management Query | [learn.microsoft.com](https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage) |
| Cost Management Forecast | [learn.microsoft.com](https://learn.microsoft.com/en-us/rest/api/cost-management/forecast/usage) |
| Cost Management Budgets | [learn.microsoft.com](https://learn.microsoft.com/en-us/rest/api/cost-management/budgets) |
| Cost Management Alerts | [learn.microsoft.com](https://learn.microsoft.com/en-us/rest/api/cost-management/alerts) |
| Azure Advisor | [learn.microsoft.com](https://learn.microsoft.com/en-us/rest/api/advisor/recommendations) |
| Azure Resource Graph | [learn.microsoft.com](https://learn.microsoft.com/en-us/rest/api/azureresourcegraph/resources) |
| Azure Updates RSS | [learn.microsoft.com](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-services-resource-providers) |

## Comparison with AWS MCP Server

| Feature | AWS MCP | This Server |
|---------|---------|-------------|
| Cost queries | Cost Explorer API | Cost Management Query API |
| Forecasts | Cost Explorer | Cost Management Forecast API |
| Budgets | AWS Budgets | Cost Management Budgets API |
| Anomaly detection | Cost Anomaly Detection | Native API + heuristic fallback |
| Personalised updates | — | Azure Updates Intelligence (RSS + Resource Graph) |
| PDF reports | — | Colour-coded PDF with executive summary |
| Remote access | — | Streamable HTTP transport |
| Recommendations | Cost Optimization Hub, Compute Optimizer | Azure Advisor (Cost category) |
| Storage analysis | S3 Storage Lens | *(not yet — planned)* |
| Output format | Natural language | Structured JSON |
