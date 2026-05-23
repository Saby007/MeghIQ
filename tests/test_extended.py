"""Extended smoke test — exercises all major MCP tool categories."""

import json
import httpx
import sys

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


def main():
    client = httpx.Client(follow_redirects=True, timeout=90)
    passed = 0
    failed = 0

    # ── Initialize ───────────────────────────────────────────────────
    r = client.post(MCP, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "extended-test", "version": "1.0"},
        },
    }, headers=HEADERS)
    sid = r.headers.get("mcp-session-id", "")
    hdrs = {**HEADERS}
    if sid:
        hdrs["mcp-session-id"] = sid

    client.post(MCP, json={
        "jsonrpc": "2.0", "method": "notifications/initialized",
    }, headers=hdrs)

    # ── Tool tests ───────────────────────────────────────────────────
    tools = [
        ("list_budgets_tool", {}),
        ("list_cost_recommendations_tool", {}),
        ("list_cost_alerts_tool", {}),
        ("get_cost_forecast_tool", {"forecast_days": 7}),
        ("get_personalized_azure_updates_tool", {}),
        ("list_anomalies_tool", {}),
        ("get_service_utilization_tool", {}),
        ("search_azure_updates_history_tool", {"query": "virtual machines"}),
    ]

    for i, (name, args) in enumerate(tools, start=10):
        print(f"Testing {name}...")
        try:
            r = client.post(MCP, json={
                "jsonrpc": "2.0", "id": i, "method": "tools/call",
                "params": {"name": name, "arguments": args},
            }, headers=hdrs)
            data = parse_sse(r.text)
            if data and "result" in data:
                content = data["result"].get("content", [])
                if content:
                    txt = content[0].get("text", "")
                    try:
                        p = json.loads(txt)
                        status = p.get("status", "?")
                        meta = p.get("metadata", {})
                        # Print key metadata
                        extra = ""
                        if "total_budgets" in meta:
                            extra = f", budgets={meta['total_budgets']}"
                        elif "total_recommendations" in meta:
                            extra = f", recommendations={meta['total_recommendations']}"
                        elif "total_alerts" in meta:
                            extra = f", alerts={meta['total_alerts']}"
                        elif "currency" in meta:
                            extra = f", currency={meta['currency']}"
                        elif "total_sections" in meta:
                            extra = f", sections={meta['total_sections']}"
                        elif "total_anomalies" in meta:
                            extra = f", anomalies={meta['total_anomalies']}"
                        elif "total_results" in meta:
                            extra = f", results={meta['total_results']}"
                        print(f"  [PASS] status={status}{extra}")
                        passed += 1
                    except json.JSONDecodeError:
                        print(f"  [PASS] non-JSON response (ok): {txt[:80]}")
                        passed += 1
                else:
                    print(f"  [WARN] empty content")
                    failed += 1
            elif data and "error" in data:
                print(f"  [FAIL] {data['error'].get('message', str(data['error']))[:150]}")
                failed += 1
            else:
                print(f"  [WARN] unexpected: {r.text[:100]}")
                failed += 1
        except Exception as e:
            print(f"  [FAIL] exception: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Extended test: {passed} passed, {failed} failed out of {len(tools)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
