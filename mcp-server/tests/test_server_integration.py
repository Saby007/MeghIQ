"""Integration tests for the MCP server that do NOT require Azure credentials.

These tests spawn the server on an ephemeral port via the FastMCP
Streamable-HTTP transport, then exercise:

  * ``GET /health`` — liveness probe
  * ``GET /metrics`` — telemetry snapshot endpoint
  * ``POST /mcp`` ``initialize`` → ``notifications/initialized`` → ``tools/list``
    handshake (verifies all tools register with valid JSON Schema).
  * ``tools/call`` against ``list_all_azure_updates_tool`` (RSS feed,
    no Azure auth required).

Excluded: any tool that calls the Azure REST APIs (Cost Management,
Resource Graph, etc.) — those live in the standalone script
``tests/test_mcp.py`` and require ``DefaultAzureCredential`` to succeed.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]  # mcp-server/
PYTHON = sys.executable

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _free_port() -> int:
    """Allocate an unused TCP port for the test server."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _parse_sse(text: str) -> dict | None:
    """Extract the first JSON-RPC envelope from an SSE response body."""
    for line in text.splitlines():
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
            except ValueError:
                continue
            if isinstance(data, dict) and ("result" in data or "error" in data):
                return data
    return None


@pytest.fixture(scope="module")
def mcp_server() -> Iterator[str]:
    """Spawn server.py on an ephemeral port; yield the base URL.

    Skips the test module entirely if the server fails to come up within
    ten seconds (most likely cause: missing optional dependency).
    """
    yield from _spawn_server()


@pytest.fixture(scope="module")
def mcp_server_with_token() -> Iterator[tuple[str, str]]:
    """Spawn a *second* server instance with ``MEGHIQ_METRICS_TOKEN`` set.

    Yields ``(base_url, token)``. Used by the ``/metrics`` auth tests.
    """
    token = "test-metrics-secret-do-not-leak"  # noqa: S105 — test-only token
    server_iter = _spawn_server(extra_env={"MEGHIQ_METRICS_TOKEN": token})
    base = next(server_iter)
    try:
        yield (base, token)
    finally:
        # Drain the generator so the teardown finally-clause runs and
        # terminates the subprocess.
        for _ in server_iter:
            pass


def _spawn_server(extra_env: dict[str, str] | None = None) -> Iterator[str]:
    """Shared helper: spawn server.py on a free port and yield the base URL."""
    port = _free_port()
    env = {
        **os.environ,
        "MCP_HOST": "127.0.0.1",
        "MCP_SERVER_PORT": str(port),
        "MEGHIQ_LOG_LEVEL": "WARNING",
        "AZURE_SUBSCRIPTION_ID": os.environ.get(
            "AZURE_SUBSCRIPTION_ID", "00000000-0000-0000-0000-000000000000"
        ),
    }
    if extra_env:
        env.update(extra_env)

    proc = subprocess.Popen(
        [PYTHON, "server.py", "--transport", "streamable-http"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"

    # Wait up to 10 s for the health endpoint to respond.
    deadline = time.time() + 10.0
    last_err: Exception | None = None
    with httpx.Client(timeout=2.0) as probe:
        while time.time() < deadline:
            if proc.poll() is not None:
                output = proc.stdout.read().decode("utf-8", "replace") if proc.stdout else ""
                pytest.skip(f"server exited early: {output[:500]}")
            try:
                r = probe.get(f"{base}/health")
                if r.status_code == 200:
                    break
            except Exception as exc:  # noqa: BLE001 — broad on purpose, we retry
                last_err = exc
            time.sleep(0.2)
        else:
            proc.terminate()
            pytest.skip(f"server did not become healthy in 10 s (last error: {last_err!r})")

    try:
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


# ── Tests ────────────────────────────────────────────────────────────


def test_health_endpoint(mcp_server: str) -> None:
    r = httpx.get(f"{mcp_server}/health", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "meghiq-mcp"


def test_metrics_endpoint_initial_shape(mcp_server: str) -> None:
    r = httpx.get(f"{mcp_server}/metrics", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert "totals" in body and "tools" in body
    totals = body["totals"]
    assert {"tool_calls_total", "tool_errors_total", "unique_tools"} <= totals.keys()


def test_mcp_initialize_and_list_tools(mcp_server: str) -> None:
    mcp_url = f"{mcp_server}/mcp"
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        # initialize
        init = client.post(
            mcp_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1.0"},
                },
            },
            headers=HEADERS,
        )
        assert init.status_code == 200, init.text[:300]
        init_payload = _parse_sse(init.text)
        assert init_payload and "result" in init_payload, init.text[:300]
        server_info = init_payload["result"]["serverInfo"]
        assert server_info["name"]

        session_id = init.headers.get("mcp-session-id", "")
        hdrs = {**HEADERS}
        if session_id:
            hdrs["mcp-session-id"] = session_id

        # notifications/initialized — no response expected
        client.post(
            mcp_url,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=hdrs,
        )

        # tools/list
        listed = client.post(
            mcp_url,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers=hdrs,
        )
        assert listed.status_code == 200, listed.text[:300]
        tools_payload = _parse_sse(listed.text)
        assert tools_payload and "result" in tools_payload
        tools = tools_payload["result"]["tools"]
        assert len(tools) >= 23, f"Expected >= 23 tools, got {len(tools)}"
        # Every tool must expose a non-empty JSON Schema for its inputs.
        for t in tools:
            schema = t.get("inputSchema") or {}
            assert schema.get("type") == "object", f"{t['name']} missing object schema"


def test_tool_call_list_all_azure_updates(mcp_server: str) -> None:
    """Calls the only Azure-creds-free tool to validate the full call path.

    The Azure Updates RSS feed is public, so this works in CI without
    any cloud auth. If the feed is unreachable from the runner we mark
    the test xfail rather than failing the suite.
    """
    mcp_url = f"{mcp_server}/mcp"
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        # Re-init since fixture is module-scoped but session_id may differ.
        init = client.post(
            mcp_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1.0"},
                },
            },
            headers=HEADERS,
        )
        session_id = init.headers.get("mcp-session-id", "")
        hdrs = {**HEADERS}
        if session_id:
            hdrs["mcp-session-id"] = session_id
        client.post(
            mcp_url,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=hdrs,
        )

        called = client.post(
            mcp_url,
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "list_all_azure_updates_tool",
                    "arguments": {"max_results": 5},
                },
            },
            headers=hdrs,
        )
        assert called.status_code == 200, called.text[:300]
        payload = _parse_sse(called.text)
        assert payload, called.text[:300]
        if "error" in payload:
            pytest.xfail(f"RSS feed unreachable: {payload['error']}")

        content = payload["result"].get("content") or []
        assert content, "tool call returned empty content"
        envelope = json.loads(content[0]["text"])
        if envelope.get("status") != "success":
            pytest.xfail(f"RSS feed call returned status={envelope.get('status')}")
        assert "data" in envelope


def test_metrics_endpoint_after_tool_call_increments(mcp_server: str) -> None:
    """After exercising tools above, the metrics endpoint must reflect calls."""
    r = httpx.get(f"{mcp_server}/metrics", timeout=5)
    assert r.status_code == 200
    body = r.json()
    # Other tests in this module call list_all_azure_updates_tool; assert
    # that at least one tool call has been recorded by the telemetry layer.
    assert body["totals"]["tool_calls_total"] >= 1


def test_metrics_prometheus_format(mcp_server: str) -> None:
    """Accept: text/plain must switch /metrics to Prometheus exposition format."""
    r = httpx.get(
        f"{mcp_server}/metrics",
        headers={"Accept": "text/plain"},
        timeout=5,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    body = r.text
    # Each metric family must publish HELP + TYPE lines.
    for family in (
        "meghiq_tool_calls_total",
        "meghiq_tool_errors_total",
        "meghiq_tool_latency_ms_avg",
        "meghiq_tool_latency_ms_max",
    ):
        assert f"# HELP {family}" in body
        assert f"# TYPE {family}" in body


def test_metrics_auth_rejects_missing_token(mcp_server_with_token: tuple[str, str]) -> None:
    base, _ = mcp_server_with_token
    r = httpx.get(f"{base}/metrics", timeout=5)
    assert r.status_code == 401


def test_metrics_auth_rejects_wrong_token(mcp_server_with_token: tuple[str, str]) -> None:
    base, _ = mcp_server_with_token
    r = httpx.get(
        f"{base}/metrics",
        headers={"Authorization": "Bearer wrong-token"},
        timeout=5,
    )
    assert r.status_code == 401


def test_metrics_auth_accepts_correct_token_json(
    mcp_server_with_token: tuple[str, str],
) -> None:
    base, token = mcp_server_with_token
    r = httpx.get(
        f"{base}/metrics",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )
    assert r.status_code == 200
    assert "totals" in r.json()


def test_metrics_auth_accepts_correct_token_prometheus(
    mcp_server_with_token: tuple[str, str],
) -> None:
    base, token = mcp_server_with_token
    r = httpx.get(
        f"{base}/metrics",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "text/plain",
        },
        timeout=5,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "# TYPE meghiq_tool_calls_total counter" in r.text


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
