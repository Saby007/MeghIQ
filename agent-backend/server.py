"""MeghIQ Agent Backend — HTTP Streamable AG-UI server.

Exposes a FastAPI endpoint (POST, NDJSON streaming) that connects:
  Angular Chat UI  →  model-router Agent  →  MCP Server (cost tools)

Uses HTTP Streamable transport (newline-delimited JSON) instead of SSE.
"""

import asyncio
import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.ag_ui import AgentFrameworkAgent
from agent_framework.azure import AzureOpenAIResponsesClient
from pydantic import BaseModel

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ENDPOINT = os.environ["AZURE_FOUNDRY_PROJECT_ENDPOINT"]
DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "model-router")
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "https://meghiq-mcp-server.azurewebsites.net/mcp")

SYSTEM_INSTRUCTIONS = """\
You are MeghIQ, an Azure cost optimization advisor.

Your capabilities (via MCP tools):
1. **get_top_cost_services** — List ALL Azure services with their costs in a subscription (sorted by spend).
2. **get_azure_updates** — Fetch recent Azure Updates (new features, pricing changes, deprecations) for a specific service.
3. **get_service_utilization** — Check utilization metrics (CPU, storage, throughput) for resources of a given service to find underutilized or over-provisioned resources.

Date handling:
- The user will indicate a date range in their message like [Date range: This Month (MonthToDate)] or [Date range: Last Month (TheLastMonth)] or [Date range: Custom from YYYY-MM-DD to YYYY-MM-DD].
- Pass the appropriate time_period parameter to get_top_cost_services:
  - "MonthToDate" for This Month
  - "TheLastMonth" for Last Month  
  - "Custom" for custom date ranges
- Always mention the date period you used in your response.

Workflow:
- When asked about costs or "all resources", call get_top_cost_services with the correct time_period and present ALL services in a Markdown table.
- When asked for an "Optimization report (top 3)", first get all costs, identify the top 3 most expensive, then run get_azure_updates and get_service_utilization for those top 3 services.
- Provide clear, actionable recommendations with estimated savings when possible.

Formatting rules:
- **Default to Markdown tables** when presenting cost data from get_top_cost_services. Use columns like: | # | Service | Cost (USD) | % of Total |
- Include a **Total** row at the bottom of cost tables.
- Only use a different format (bullet points, prose, etc.) if the user explicitly asks for it.
- Always explain your reasoning and cite specific data from the tools.
- Prioritize recommendations by potential impact.
- If a tool call fails, explain the limitation and suggest alternatives.
"""

# ---------------------------------------------------------------------------
# MCP Tool — connects to the running MCP server
# ---------------------------------------------------------------------------
mcp_tool = MCPStreamableHTTPTool(
    name="meghiq-mcp",
    url=MCP_SERVER_URL,
    request_timeout=120,
)

# ---------------------------------------------------------------------------
# Azure OpenAI client via Foundry project
# ---------------------------------------------------------------------------
client = AzureOpenAIResponsesClient(
    project_endpoint=PROJECT_ENDPOINT,
    deployment_name=DEPLOYMENT_NAME,
    credential=DefaultAzureCredential(),
)

# ---------------------------------------------------------------------------
# Agent: LLM + MCP tools
# ---------------------------------------------------------------------------
agent = Agent(
    client,
    SYSTEM_INSTRUCTIONS,
    name="MeghIQ",
    tools=[mcp_tool],
)

# Wrap in AgentFrameworkAgent to get AG-UI event stream
protocol_runner = AgentFrameworkAgent(agent=agent)

# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    messages: list[dict]
    thread_id: str | None = None
    run_id: str | None = None
    state: dict | None = None
    tools: list[dict] | None = None


# ---------------------------------------------------------------------------
# FastAPI app with HTTP Streamable endpoint
# ---------------------------------------------------------------------------

_mcp_ready = asyncio.Event()


async def _connect_mcp():
    """Connect MCP tool as an independent top-level task (avoids lifespan cancel scope bug)."""
    try:
        await mcp_tool.connect()
        _mcp_ready.set()
        logger.info("MCP connected: tools loaded")
    except Exception:
        logger.exception("MCP connect failed — will retry on first request")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Fire MCP connect as a standalone task, not nested in lifespan scope."""
    task = asyncio.create_task(_connect_mcp())
    yield
    task.cancel()
    try:
        await mcp_tool.disconnect()
    except Exception:
        pass


app = FastAPI(
    title="MeghIQ Agent Backend",
    description="HTTP Streamable AG-UI server for Azure cost optimization",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # Angular dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/")
async def chat(request_body: ChatRequest) -> StreamingResponse:
    """HTTP Streamable endpoint — streams AG-UI events as NDJSON."""
    input_data = request_body.model_dump(exclude_none=True)

    async def event_generator() -> AsyncGenerator[str, None]:
        max_retries = 3
        retry_delays = [5, 15, 30]

        # Wait for MCP to be ready (connected in background task)
        if not _mcp_ready.is_set():
            try:
                await asyncio.wait_for(_mcp_ready.wait(), timeout=60)
            except asyncio.TimeoutError:
                yield json.dumps({"type": "RUN_ERROR", "message": "MCP server connection timed out. Please try again."}) + "\n"
                return

        for attempt in range(max_retries + 1):
            try:
                async for event in protocol_runner.run(input_data):
                    payload = event.model_dump(exclude_none=True) if hasattr(event, "model_dump") else {"type": "UNKNOWN"}
                    yield json.dumps(payload) + "\n"
                return  # success — done streaming
            except Exception as exc:
                is_rate_limit = "429" in str(exc)
                if is_rate_limit and attempt < max_retries:
                    delay = retry_delays[attempt]
                    logger.warning("Rate limited (429), retrying in %ds (attempt %d/%d)", delay, attempt + 1, max_retries)
                    yield json.dumps({"type": "TEXT_MESSAGE_CONTENT", "delta": f"\n\n⏳ Rate limited by Azure OpenAI. Retrying in {delay}s…\n\n"}) + "\n"
                    await asyncio.sleep(delay)
                    continue
                logger.exception("Streaming failed")
                msg = "Rate limited by Azure OpenAI. Please wait a moment and try again." if is_rate_limit else "An internal error occurred."
                yield json.dumps({"type": "RUN_ERROR", "message": msg}) + "\n"
                return

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("AGUI_SERVER_PORT", "5100"))
    uvicorn.run("server:app", host="127.0.0.1", port=port)
