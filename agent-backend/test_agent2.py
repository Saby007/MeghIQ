"""Test agent backend end-to-end on port 5101."""
import httpx
import json

r = httpx.post(
    "http://127.0.0.1:5101/",
    json={
        "messages": [
            {
                "role": "user",
                "content": "What are the top 5 most expensive Azure services in my subscription?",
            }
        ]
    },
    timeout=120.0,
)

print("Status:", r.status_code)
for line in r.text.strip().split("\n"):
    if line.strip():
        evt = json.loads(line)
        etype = evt.get("type", "?")
        preview = json.dumps(evt)[:300]
        print(f"  [{etype}] {preview}")
