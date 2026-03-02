"""
Orchestrator - SQL Chatbot
FastAPI backend that acts as MCP client, connects to the MCP server,
and uses GPT-4.1 to orchestrate tool calls and produce plain English answers.
"""

import os
import json
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp")

# ── Credential ────────────────────────────────────────────────────────
credential = DefaultAzureCredential()

# ── Azure OpenAI client ──────────────────────────────────────────────
openai_client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    azure_ad_token_provider=lambda: credential.get_token(
        "https://cognitiveservices.azure.com/.default"
    ).token,
    api_version=AZURE_OPENAI_API_VERSION,
)

# ── Conversation history (in-memory per session) ─────────────────────
conversations: dict[str, list] = {}


# ── FastAPI app ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    print(f"Orchestrator starting. MCP Server URL: {MCP_SERVER_URL}")
    yield
    print("Orchestrator shutting down.")


app = FastAPI(
    title="SQL Chatbot Orchestrator",
    description="Orchestrates GPT-4.1 and MCP tools to answer database questions",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    answer: str
    sql_query: Optional[str] = None
    raw_data: Optional[dict] = None
    session_id: str


# ── MCP Tool Discovery & Invocation ──────────────────────────────────
async def discover_mcp_tools() -> list[dict]:
    """Connect to MCP server and discover available tools."""
    async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tools = []
            for tool in tools_result.tools:
                schema = tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}}
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": schema,
                    },
                })
            return tools


async def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Call a specific tool on the MCP server."""
    async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            # Extract text from result content
            texts = []
            for content in result.content:
                if hasattr(content, "text"):
                    texts.append(content.text)
            return "\n".join(texts)


# ── Chat Endpoint ─────────────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint. Receives a natural language message,
    uses GPT-4.1 to decide which MCP tools to call, executes them,
    and returns a plain English response.
    """
    session_id = request.session_id or "default"

    # Initialize conversation if new
    if session_id not in conversations:
        conversations[session_id] = [
            {
                "role": "system",
                "content": (
                    "You are a helpful database assistant that answers questions about data "
                    "stored in an Azure SQL database. You have access to tools that can query "
                    "the database. When the user asks about data, use the query_database tool "
                    "to get the answer. Always present the results in clear, well-formatted "
                    "plain English. If the data is tabular, format it nicely. Include the SQL "
                    "query used for transparency. If you get an error, explain what went wrong "
                    "and suggest how to fix the question."
                ),
            }
        ]

    # Add user message to conversation
    conversations[session_id].append({"role": "user", "content": request.message})

    try:
        # Discover MCP tools
        tools = await discover_mcp_tools()

        # Call GPT-4.1 with tools
        messages = conversations[session_id].copy()
        response = openai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            temperature=0.3,
        )

        assistant_msg = response.choices[0].message
        sql_query = None
        raw_data = None

        # Handle tool calls (loop for multi-step reasoning)
        max_iterations = 5
        iteration = 0
        while assistant_msg.tool_calls and iteration < max_iterations:
            iteration += 1
            # Add assistant message with tool calls
            messages.append(assistant_msg.model_dump())

            # Execute each tool call
            for tool_call in assistant_msg.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                print(f"  Calling MCP tool: {fn_name}({fn_args})")
                tool_result = await call_mcp_tool(fn_name, fn_args)

                # Parse out SQL query and raw data for the response
                try:
                    parsed = json.loads(tool_result)
                    if parsed.get("sql_query"):
                        sql_query = parsed["sql_query"]
                    if parsed.get("columns") and parsed.get("rows"):
                        raw_data = {
                            "columns": parsed["columns"],
                            "rows": parsed["rows"],
                            "row_count": parsed.get("row_count", len(parsed["rows"])),
                        }
                except (json.JSONDecodeError, KeyError):
                    pass

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    }
                )

            # Call GPT-4.1 again with tool results to get final answer
            response = openai_client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                temperature=0.3,
            )
            assistant_msg = response.choices[0].message

        # Get the final text answer
        answer = assistant_msg.content or "I couldn't generate a response."

        # Save assistant response to conversation history
        conversations[session_id].append({"role": "assistant", "content": answer})

        return ChatResponse(
            answer=answer,
            sql_query=sql_query,
            raw_data=raw_data,
            session_id=session_id,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "mcp_server_url": MCP_SERVER_URL}


@app.delete("/api/chat/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    if session_id in conversations:
        del conversations[session_id]
    return {"status": "cleared", "session_id": session_id}


# ── Entry point ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("ORCHESTRATOR_PORT", "8000"))
    print(f"Starting Orchestrator on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
