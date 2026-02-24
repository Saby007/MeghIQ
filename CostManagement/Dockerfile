# Azure Cost Management MCP Server — Streamable HTTP Container
# Exposes the MCP server at /mcp via Streamable HTTP transport

FROM python:3.12-slim

# Metadata
LABEL maintainer="SfMC Adobe Team"
LABEL description="Azure Cost Management MCP Server with Streamable HTTP transport"

# Prevent Python from buffering stdout/stderr (important for container logs)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set transport to streamable-http for containerised deployment
ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000

# Log level (override at runtime if needed)
ENV AZURE_COST_MCP_LOG_LEVEL=INFO

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Expose the MCP Streamable HTTP port
EXPOSE 8000

# Health check — the /mcp endpoint should respond
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/mcp'); assert r.status_code < 500" || exit 1

# Run the MCP server in streamable-http mode
CMD ["azure-cost-mcp", "--transport", "streamable-http"]
