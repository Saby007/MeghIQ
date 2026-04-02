"""Quick test: query Azure Cost Management with retry."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv

load_dotenv()

from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    ExportType,
    QueryAggregation,
    QueryDataset,
    QueryDefinition,
    QueryGrouping,
    TimeframeType,
)

cred = DefaultAzureCredential()
client = CostManagementClient(cred)
sub = os.environ["AZURE_SUBSCRIPTION_ID"]
scope = f"/subscriptions/{sub}"

qd = QueryDefinition(
    type=ExportType.ACTUAL_COST,
    timeframe=TimeframeType.MONTH_TO_DATE,
    dataset=QueryDataset(
        granularity=None,
        aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
        grouping=[QueryGrouping(type="Dimension", name="ServiceName")],
    ),
)

for attempt in range(5):
    try:
        print(f"Attempt {attempt + 1}...")
        result = client.query.usage(scope=scope, parameters=qd)
        print(f"Success! Rows: {len(result.rows) if result.rows else 0}")
        if result.rows:
            for row in sorted(result.rows, key=lambda r: float(r[0]), reverse=True)[:5]:
                print(f"  {row[1]}: {float(row[0]):.2f} {row[2]}")
        break
    except Exception as e:
        wait = 5 * (2**attempt)  # 5, 10, 20, 40, 80
        print(f"  Error: {type(e).__name__}: {str(e)[:150]}")
        print(f"  Waiting {wait}s before retry...")
        time.sleep(wait)
