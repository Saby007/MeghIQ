"""Quick smoke test for the MeghIQ MCP server."""

import json
import httpx

BASE = "http://127.0.0.1:8000"
MCP  = f"{BASE}/mcp"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _parse_sse(text: str) -> dict | None:
    """Extract the first JSON-RPC result from an SSE stream."""
    for line in text.splitlines():
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if "result" in data or "error" in data:
                return data
    return None


def main():
    client = httpx.Client(follow_redirects=True, timeout=30)

    # ── 1. Health check ──────────────────────────────────────────────
    r = client.get(f"{BASE}/health")
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    print(f"[PASS] Health check: {r.json()}")

    # ── 2. MCP Initialize ───────────────────────────────────────────
    r = client.post(MCP, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }, headers=HEADERS)
    assert r.status_code == 200, f"Init failed: {r.status_code} {r.text[:200]}"
    init_data = _parse_sse(r.text)
    assert init_data and "result" in init_data, f"Bad init response: {r.text[:300]}"
    server_info = init_data["result"]["serverInfo"]
    print(f"[PASS] Initialize: {server_info['name']} v{server_info['version']}")

    session_id = r.headers.get("mcp-session-id", "")
    hdrs = {**HEADERS}
    if session_id:
        hdrs["mcp-session-id"] = session_id

    # ── 3. Send initialized notification ─────────────────────────────
    client.post(MCP, json={
        "jsonrpc": "2.0", "method": "notifications/initialized",
    }, headers=hdrs)
    print("[PASS] Initialized notification sent")

    # ── 4. List tools ────────────────────────────────────────────────
    r = client.post(MCP, json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
    }, headers=hdrs)
    assert r.status_code == 200, f"tools/list failed: {r.status_code}"
    tools_data = _parse_sse(r.text)
    assert tools_data and "result" in tools_data
    tools = tools_data["result"]["tools"]
    print(f"[PASS] tools/list: {len(tools)} tools registered")
    for t in tools:
        print(f"       - {t['name']}")

    # ── 5. Call list_all_azure_updates_tool (no Azure creds needed) ──
    print("\n[TEST] Calling list_all_azure_updates_tool (RSS feed)...")
    r = client.post(MCP, json={
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {
            "name": "list_all_azure_updates_tool",
            "arguments": {"max_results": 5},
        },
    }, headers=hdrs)
    assert r.status_code == 200, f"Tool call failed: {r.status_code}"
    call_data = _parse_sse(r.text)
    if call_data and "result" in call_data:
        content = call_data["result"].get("content", [])
        if content:
            text_content = content[0].get("text", "")
            parsed = json.loads(text_content)
            status = parsed.get("status", "unknown")
            if status == "success":
                count = parsed.get("metadata", {}).get("total_updates", 0)
                print(f"[PASS] list_all_azure_updates_tool: {count} updates returned")
            else:
                print(f"[WARN] Tool returned status={status}: {text_content[:200]}")
        else:
            print(f"[WARN] Empty content: {call_data}")
    elif call_data and "error" in call_data:
        print(f"[FAIL] Tool error: {call_data['error']}")
    else:
        print(f"[WARN] Unexpected response: {r.text[:300]}")

    # ── 6. Call query_subscription_costs_tool (needs Azure creds) ────
    print("\n[TEST] Calling query_subscription_costs_tool (Azure API)...")
    r = client.post(MCP, json={
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {
            "name": "query_subscription_costs_tool",
            "arguments": {"timeframe": "MonthToDate", "granularity": "None"},
        },
    }, headers=hdrs)
    assert r.status_code == 200, f"Tool call HTTP failed: {r.status_code}"
    call_data = _parse_sse(r.text)
    if call_data and "result" in call_data:
        content = call_data["result"].get("content", [])
        if content:
            text_content = content[0].get("text", "")
            try:
                parsed = json.loads(text_content)
                status = parsed.get("status", "unknown")
                if status == "success":
                    data = parsed.get("data", [])
                    row_count = len(data) if isinstance(data, list) else len(data.get("rows", []))
                    currency = parsed.get("metadata", {}).get("currency", "?")
                    print(f"[PASS] query_subscription_costs_tool: {row_count} rows, currency={currency}")
                else:
                    print(f"[INFO] Tool returned status={status} (may need Azure creds)")
            except json.JSONDecodeError:
                print(f"[INFO] Non-JSON response (may need Azure creds): {text_content[:150]}")
    elif call_data and "error" in call_data:
        err = call_data["error"]
        print(f"[INFO] Expected error (Azure creds): {err.get('message', str(err))[:150]}")
    else:
        print(f"[WARN] Unexpected: {r.text[:200]}")

    print("\n" + "=" * 60)
    print("MCP Server smoke test complete!")


if __name__ == "__main__":
    main()
