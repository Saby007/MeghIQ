# SQL Chatbot — Talk To Your Database

A 3-tier chatbot application that lets you interact with an Azure SQL database
using natural language. Powered by **Microsoft Foundry GPT-4.1**.

## Architecture

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────────────┐
│  Angular UI     │────▶│  Orchestrator (FastAPI)   │────▶│  MCP Server (Python)    │
│  localhost:4200  │◀────│  localhost:8000           │◀────│  localhost:8001          │
│                 │     │  + MCP Client             │     │  + GPT-4.1 (SQL Gen)    │
│                 │     │  + GPT-4.1 (Summarizer)   │     │  + Azure SQL (pyodbc)   │
└─────────────────┘     └──────────────────────────┘     └─────────────────────────┘
```

## Prerequisites

- Python 3.11+
- Node.js 18+ and Angular CLI
- Azure CLI (logged in with `az login`)
- ODBC Driver 18 for SQL Server

## Quick Start

### 1. Start MCP Server (Terminal 1)
```bash
cd mcp-server
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
python server.py
```

### 2. Start Orchestrator (Terminal 2)
```bash
cd orchestrator
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
python app.py
```

### 3. Start Angular Frontend (Terminal 3)
```bash
cd frontend
npm install
ng serve
```

Open http://localhost:4200 in your browser and start chatting!

## Azure Resources

| Resource | Location | Details |
|----------|----------|---------|
| Microsoft Foundry (AIServices) | East US 2 | `chatbot-foundry-eastus2` |
| Foundry Project | East US 2 | `chatbot-project` |
| GPT-4.1 Deployment | East US 2 | `gpt-41-deployment` (GlobalStandard, 50K TPM) |
| Azure SQL Server | Central India | `chatbot-sql-centralindia.database.windows.net` |
| Database | Central India | `SampleDB` (AdventureWorksLT sample data) |

## Auth

All Azure services use **Entra ID (DefaultAzureCredential)** — no API keys.
Run `az login` before starting the servers.
