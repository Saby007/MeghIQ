#!/bin/bash
# Azure App Service startup script
# The PORT env var is set by Azure App Service
export MCP_SERVER_PORT="${PORT:-8000}"
export MCP_HOST="0.0.0.0"
python server.py --transport streamable-http
