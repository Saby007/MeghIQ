"""Verbose MCP test — prints full tool responses for inspection."""

import json
import httpx

BASE = "http://127.0.0.1:8000"
MCP = f"{BASE}/mcp"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def parse_sse(text: str) -> dict | None:
    for line in text.splitlines():
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if "result" in data or "error" in data:
                return data
    return None


def call_tool(client, hdrs, tool_id, name, args):
    """Call an MCP tool and return the parsed JSON result."""
    r = client.post(MCP, json={
        "jsonrpc": "2.0", "id": tool_id, "method": "tools/call",
        "params": {"name": name, "arguments": args},
    }, headers=hdrs)
    data = parse_sse(r.text)
    if data and "result" in data:
        content = data["result"].get("content", [])
        if content:
            txt = content[0].get("text", "")
            try:
                return json.loads(txt)
            except json.JSONDecodeError:
                return {"raw_text": txt[:500]}
    elif data and "error" in data:
        return {"error": data["error"]}
    return {"unexpected": r.text[:300]}


def pp(obj, max_lines=40):
    """Pretty-print JSON, truncating if too long."""
    s = json.dumps(obj, indent=2, default=str)
    lines = s.split("\n")
    if len(lines) > max_lines:
        print("\n".join(lines[:max_lines]))
        print(f"  ... ({len(lines) - max_lines} more lines)")
    else:
        print(s)


def main():
    client = httpx.Client(follow_redirects=True, timeout=90)

    # Initialize MCP session
    r = client.post(MCP, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "verbose-test", "version": "1.0"},
        },
    }, headers=HEADERS)
    init = parse_sse(r.text)
    sid = r.headers.get("mcp-session-id", "")
    hdrs = {**HEADERS}
    if sid:
        hdrs["mcp-session-id"] = sid
    client.post(MCP, json={
        "jsonrpc": "2.0", "method": "notifications/initialized",
    }, headers=hdrs)

    server = init["result"]["serverInfo"]
    print(f"Server: {server['name']} v{server['version']}")
    print(f"Session: {sid[:20]}...")
    print("=" * 70)

    # ── Test 1: Subscription Costs ───────────────────────────────────
    print("\n[1] query_subscription_costs_tool (MonthToDate, by ServiceName)")
    result = call_tool(client, hdrs, 10, "query_subscription_costs_tool", {
        "timeframe": "MonthToDate",
        "granularity": "None",
        "group_by": "ServiceName",
    })
    pp(result)

    # ── Test 2: Cost Forecast ────────────────────────────────────────
    print("\n[2] get_cost_forecast_tool (7-day forecast)")
    result = call_tool(client, hdrs, 11, "get_cost_forecast_tool", {
        "forecast_days": 7,
        "granularity": "Daily",
    })
    pp(result)

    # ── Test 3: Budgets ──────────────────────────────────────────────
    print("\n[3] list_budgets_tool")
    result = call_tool(client, hdrs, 12, "list_budgets_tool", {})
    pp(result)

    # ── Test 4: Recommendations ──────────────────────────────────────
    print("\n[4] list_cost_recommendations_tool")
    result = call_tool(client, hdrs, 13, "list_cost_recommendations_tool", {})
    pp(result)

    # ── Test 5: Alerts ───────────────────────────────────────────────
    print("\n[5] list_cost_alerts_tool")
    result = call_tool(client, hdrs, 14, "list_cost_alerts_tool", {})
    pp(result)

    # ── Test 6: Anomalies ────────────────────────────────────────────
    print("\n[6] list_anomalies_tool")
    result = call_tool(client, hdrs, 15, "list_anomalies_tool", {})
    pp(result)

    # ── Test 7: Azure Updates (RSS) ──────────────────────────────────
    print("\n[7] list_all_azure_updates_tool (max 3)")
    result = call_tool(client, hdrs, 16, "list_all_azure_updates_tool", {
        "max_results": 3,
    })
    pp(result)

    # ── Test 8: Personalized Updates Intel ───────────────────────────
    print("\n[8] get_personalized_azure_updates_tool")
    result = call_tool(client, hdrs, 17, "get_personalized_azure_updates_tool", {})
    pp(result, max_lines=50)

    # ── Test 9: Updates History Search ───────────────────────────────
    print("\n[9] search_azure_updates_history_tool (query='virtual machines')")
    result = call_tool(client, hdrs, 18, "search_azure_updates_history_tool", {
        "query": "virtual machines",
    })
    pp(result, max_lines=30)

    print("\n" + "=" * 70)
    print("Verbose test complete!")


if __name__ == "__main__":
    main()
