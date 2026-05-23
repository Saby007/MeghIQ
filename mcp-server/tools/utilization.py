"""Azure service utilization tool — dynamic resource discovery & metric fetching.

Uses Azure Resource Graph to discover resources by service name and Azure
Monitor's metric definitions API to dynamically determine available metrics
per resource type — no hardcoded mappings.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from auth import get_monitor_client, get_subscription_id, get_token
from response import error_response, success_response
from tools.http_utils import check_azure_response
from tools.validators import (
    sanitize_error_message,
    sanitize_kql_input,
    validate_azure_resource_id,
    validate_subscription_id,
)

logger = logging.getLogger(__name__)

RESOURCE_GRAPH_API_VERSION = "2022-10-01"
RESOURCE_GRAPH_URL = (
    "https://management.azure.com/providers/Microsoft.ResourceGraph/resources"
    f"?api-version={RESOURCE_GRAPH_API_VERSION}"
)
MONITOR_API_VERSION = "2024-02-01"
METRIC_NAMESPACES_API_VERSION = "2017-12-01-preview"
BASE_URL = "https://management.azure.com"

# Hard upper bound on the user-requestable metrics window. Azure Monitor
# itself retains standard metrics for ~93 days; allow up to that.
MAX_WINDOW_DAYS = 93

# Default window when start/end are not supplied (preserves prior behaviour).
DEFAULT_WINDOW_DAYS = 3

# Default time grain when none is supplied (preserves prior behaviour).
DEFAULT_INTERVAL = "PT1H"


def _parse_iso8601_utc(value: str) -> datetime:
    """Parse an ISO-8601 timestamp into a timezone-aware UTC datetime.

    Accepts trailing 'Z' (Zulu) as well as explicit offsets.
    """
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0)


def _resolve_time_window(
    start_time: str | None,
    end_time: str | None,
) -> tuple[datetime, datetime]:
    """Resolve and validate a user-supplied time window.

    Falls back to the prior default (last DEFAULT_WINDOW_DAYS) when both
    bounds are omitted. Enforces MAX_WINDOW_DAYS as an upper bound.
    """
    now = datetime.now(timezone.utc).replace(microsecond=0)

    end_dt = _parse_iso8601_utc(end_time) if end_time else now
    if start_time:
        start_dt = _parse_iso8601_utc(start_time)
    else:
        start_dt = end_dt - timedelta(days=DEFAULT_WINDOW_DAYS)

    if start_dt >= end_dt:
        raise ValueError("start_time must be strictly earlier than end_time")

    if (end_dt - start_dt) > timedelta(days=MAX_WINDOW_DAYS):
        raise ValueError(
            f"Requested time window exceeds maximum of {MAX_WINDOW_DAYS} days"
        )

    return start_dt, end_dt


def _auto_interval(window: timedelta) -> str:
    """Pick a sensible Azure Monitor time grain for a given window length.

    Azure Monitor caps a single metrics.list response at roughly 1440 data
    points; pick a coarser grain for longer windows to stay well under that.
    """
    if window <= timedelta(days=2):
        return "PT5M"
    if window <= timedelta(days=7):
        return "PT15M"
    if window <= timedelta(days=14):
        return "PT1H"
    if window <= timedelta(days=30):
        return "PT6H"
    return "PT12H"


async def _discover_resource_type(
    service_name: str,
    subscription_id: str,
    token: str,
) -> str | None:
    """Dynamically resolve a service name to an ARM resource type using Resource Graph.

    Queries for resources whose type contains the service name keywords,
    then returns the most common resource type found.
    """
    # Validate inputs before interpolating into KQL to prevent injection.
    safe_sub_id = validate_subscription_id(subscription_id)
    safe_search = sanitize_kql_input(service_name.lower())

    # Try an exact-ish type match first, then fall back to broader search
    query = f"""
    Resources
    | where subscriptionId == '{safe_sub_id}'
    | where type contains '{safe_search}'
       or name contains '{safe_search}'
    | summarize count() by type
    | order by count_ desc
    | limit 1
    """

    query_body = {
        "subscriptions": [safe_sub_id],
        "query": query,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            RESOURCE_GRAPH_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=query_body,
        )

    if resp.status_code != 200:
        logger.warning(
            "Resource Graph discovery returned %d (retry_after=%s)",
            resp.status_code,
            resp.headers.get("Retry-After", "-"),
        )
        return None

    data = resp.json().get("data", [])

    # Handle table format or objectArray format
    if isinstance(data, dict):
        rows = data.get("rows", [])
        columns = [c["name"] for c in data.get("columns", [])]
        records = [dict(zip(columns, row)) for row in rows]
    elif isinstance(data, list):
        records = data
    else:
        records = []

    if records:
        return records[0].get("type", "").lower()
    return None


async def _discover_metric_names(
    resource_id: str,
    token: str,
    metric_namespace: str | None = None,
    prioritize: bool = True,
    max_metrics: int = 8,
) -> list[str]:
    """Dynamically discover available metric names for a resource using Azure Monitor.

    Calls the metric definitions API to enumerate all metrics the resource supports.

    When ``metric_namespace`` is supplied, the lookup is scoped to that namespace
    (required for child namespaces such as
    ``Microsoft.Storage/storageAccounts/blobServices``).

    When ``prioritize`` is True (default), filters to utilization-relevant metrics
    by keyword scoring and caps at ``max_metrics``. When False, returns every
    metric name exposed by the namespace (still capped at ``max_metrics`` to keep
    the resulting Azure Monitor query URL within length limits) — use this when
    the caller deliberately scoped to a specific namespace and wants the full set.
    """
    url = (
        f"{BASE_URL}{resource_id}/providers/microsoft.insights/metricDefinitions"
        f"?api-version={MONITOR_API_VERSION}"
    )
    if metric_namespace:
        url += f"&metricnamespace={metric_namespace}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

    if resp.status_code != 200:
        logger.warning("Metric definitions API returned %d for %s", resp.status_code, resource_id)
        return []

    definitions = resp.json().get("value", [])
    all_names = [d.get("name", {}).get("value", "") for d in definitions]
    all_names = [n for n in all_names if n]

    if not prioritize:
        # Caller explicitly chose this namespace — return everything (capped).
        return all_names[:max_metrics]

    # Prioritize utilization-related metrics
    priority_keywords = [
        "cpu", "memory", "percentage", "percent", "utilization",
        "capacity", "used", "throughput", "requests", "connections",
        "ingress", "egress", "latency", "errors", "count",
    ]

    scored_metrics: list[tuple[int, str]] = []
    for defn in definitions:
        name = defn.get("name", {}).get("value", "")
        display_name = (defn.get("name", {}).get("localizedValue", "") or "").lower()

        # Score by how many priority keywords appear in the name
        score = sum(1 for kw in priority_keywords if kw in name.lower() or kw in display_name)
        scored_metrics.append((score, name))

    # Sort by relevance score descending, take top N
    scored_metrics.sort(key=lambda x: x[0], reverse=True)
    return [name for score, name in scored_metrics[:max_metrics] if score > 0]


async def _list_metric_namespaces(
    resource_id: str,
    token: str,
) -> list[dict[str, str]]:
    """List all metric namespaces exposed by a resource (including child namespaces).

    Returns a list of ``{"name": ..., "classification": ...}`` entries.
    ``classification`` is typically ``Platform``, ``Custom``, or ``Qos`` — callers
    usually want to filter to ``Platform`` to avoid noisy custom metrics.

    Returns an empty list when the API is unavailable or the resource has no
    metric namespaces (caller should fall back to the default namespace).
    """
    url = (
        f"{BASE_URL}{resource_id}/providers/microsoft.insights/metricNamespaces"
        f"?api-version={METRIC_NAMESPACES_API_VERSION}"
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})

    if resp.status_code != 200:
        logger.warning(
            "Metric namespaces API returned %d for %s", resp.status_code, resource_id
        )
        return []

    namespaces: list[dict[str, str]] = []
    for entry in resp.json().get("value", []):
        props = entry.get("properties") or {}
        ns = props.get("metricNamespaceName") or entry.get("name")
        if not ns:
            continue
        classification = entry.get("classification") or props.get("classification") or ""
        namespaces.append({"name": ns, "classification": classification})
    return namespaces


def _child_resource_uri_for_namespace(
    parent_resource_id: str,
    metric_namespace: str,
) -> str | None:
    """Derive the child resource URI for a sub-namespace, if one applies.

    Azure exposes some metrics on child resources whose namespace follows the
    pattern ``<ParentType>/<childCollection>`` (e.g.,
    ``Microsoft.Storage/storageAccounts/blobServices``). The corresponding child
    resource URI is ``<parent>/<childCollection>/default``.

    Returns ``None`` when the namespace does not match this pattern or doesn't
    extend the parent resource's type.
    """
    if not metric_namespace or "/" not in metric_namespace:
        return None

    # Extract the parent resource type from the resource ID
    # e.g., .../providers/Microsoft.Storage/storageAccounts/<name>
    #        -> parent_type = "Microsoft.Storage/storageAccounts"
    parts = parent_resource_id.strip("/").split("/")
    try:
        providers_idx = parts.index("providers")
    except ValueError:
        return None

    if len(parts) < providers_idx + 4:
        return None

    parent_type = f"{parts[providers_idx + 1]}/{parts[providers_idx + 2]}"
    ns_lower = metric_namespace.lower()
    parent_type_lower = parent_type.lower()

    if not ns_lower.startswith(parent_type_lower + "/"):
        return None

    child_segment = metric_namespace[len(parent_type) + 1:]
    # Only handle a single-level child (e.g. "blobServices"); deeper paths are rare.
    if "/" in child_segment:
        return None

    return f"{parent_resource_id.rstrip('/')}/{child_segment}/default"


async def get_service_utilization(
    service_name: str,
    subscription_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    interval: str | None = None,
    metric_namespace: str | None = None,
) -> str:
    """Get utilization details for a given Azure service in the subscription.

    Dynamically discovers the resource type and available metrics — no hardcoded
    mappings. Lists resources using Azure Resource Graph, discovers their metrics
    via Azure Monitor, then fetches utilization data.

    Args:
        service_name: The Azure service to query (e.g., "Storage", "Virtual Machines", "SQL").
        subscription_id: Azure subscription ID. Uses AZURE_SUBSCRIPTION_ID env var if not provided.
        start_time: Optional ISO-8601 UTC start of the metrics window. Defaults
            to ``end_time - 3 days`` to preserve the legacy behaviour.
        end_time: Optional ISO-8601 UTC end of the metrics window. Defaults to now.
        interval: Optional Azure Monitor time grain (e.g., ``PT5M``, ``PT1H``).
            Auto-selected from the window length when omitted.
        metric_namespace: Optional metric namespace to query (e.g.,
            ``Microsoft.Storage/storageAccounts/blobServices``). When omitted,
            the resource's default namespace is used.

    Returns:
        JSON string with resource list and utilization metrics for each resource.
    """
    try:
        sub_id = (
            validate_subscription_id(subscription_id)
            if subscription_id
            else get_subscription_id()
        )
        token = get_token()

        # Validate the time window once up front (raises ValueError on bad input).
        start_dt, end_dt = _resolve_time_window(start_time, end_time)
        chosen_interval = interval or _auto_interval(end_dt - start_dt)

        # Step 1: Dynamically discover resource type from service name
        resource_type = await _discover_resource_type(service_name, sub_id, token)

        if not resource_type:
            return error_response(
                f"No resources found matching service '{service_name}' "
                f"in subscription {sub_id}. Try a different service name or "
                f"check that resources of this type are deployed."
            )

        # Sanitize the resource type before re-interpolating into a new KQL
        # query (it came from a prior Resource Graph result, but defence in depth).
        safe_resource_type = sanitize_kql_input(resource_type)

        # Step 2: Query Resource Graph for resources of this type
        query = f"""
        Resources
        | where type =~ '{safe_resource_type}'
        | where subscriptionId == '{sub_id}'
        | project id, name, type, location, resourceGroup, sku, properties
        | limit 20
        """

        query_body = {
            "subscriptions": [sub_id],
            "query": query,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                RESOURCE_GRAPH_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=query_body,
            )

        if resp.status_code != 200:
            err = check_azure_response(resp, api_label="Resource Graph query")
            if err is not None:
                return err

        data = resp.json().get("data", [])

        if isinstance(data, dict):
            rows = data.get("rows", [])
            columns = [c["name"] for c in data.get("columns", [])]
            records = [dict(zip(columns, row)) for row in rows]
        elif isinstance(data, list):
            records = data
        else:
            records = []

        if not records:
            return error_response(
                f"No resources of type '{resource_type}' found in subscription {sub_id}."
            )

        # Step 3: For the first resource, discover available metrics dynamically
        first_resource_id = records[0].get("id", "")
        metric_names = await _discover_metric_names(
            first_resource_id, token, metric_namespace=metric_namespace
        )

        # Step 4: Fetch metrics for each resource
        resources: list[dict[str, Any]] = []
        for row in records:
            resource_info: dict[str, Any] = {
                "name": row.get("name", ""),
                "resource_group": row.get("resourceGroup", ""),
                "location": row.get("location", ""),
                "resource_id": row.get("id", ""),
                "sku": str(row.get("sku", "")),
            }

            if metric_names:
                metrics = await _get_resource_metrics(
                    resource_id=row.get("id", ""),
                    metric_names=metric_names,
                    subscription_id=sub_id,
                    metric_namespace=metric_namespace,
                    start_time=start_dt,
                    end_time=end_dt,
                    interval=chosen_interval,
                )
                resource_info["metrics"] = metrics
            else:
                resource_info["metrics"] = {"_note": "No utilization metrics available for this resource type"}

            resources.append(resource_info)

        return success_response(
            {
                "service": service_name,
                "resource_type": resource_type,
                "total_resources": len(resources),
                "discovered_metrics": metric_names,
                "timespan": {
                    "start": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end": end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "interval": chosen_interval,
                },
                "metric_namespace": metric_namespace,
                "resources": resources,
            },
            scope=f"subscriptions/{sub_id}",
            extra_meta={
                "subscriptionId": sub_id,
                "resourceType": resource_type,
                "metricsDiscovered": len(metric_names),
            },
        )
    except ValueError as ve:
        return error_response(sanitize_error_message(str(ve)), code="400")
    except Exception as e:
        logger.exception("get_service_utilization failed")
        return error_response(sanitize_error_message(str(e)))


async def _get_resource_metrics(
    resource_id: str,
    metric_names: list[str],
    subscription_id: str,
    metric_namespace: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    interval: str | None = None,
    aggregation: str | None = None,
) -> dict[str, Any]:
    """Fetch utilization metrics for a specific resource from Azure Monitor.

    All time/namespace/aggregation parameters are optional; omitting them
    preserves the legacy behaviour (last 3 days, PT1H, default namespace,
    ``Average,Maximum,Total`` aggregations).
    """
    if not metric_names or not resource_id:
        return {}

    monitor_client = get_monitor_client(subscription_id)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    end_dt = end_time or now
    start_dt = start_time or (end_dt - timedelta(days=DEFAULT_WINDOW_DAYS))
    interval = interval or DEFAULT_INTERVAL
    aggregation = aggregation or "Average,Maximum,Total"

    metrics_data: dict[str, Any] = {}
    list_kwargs: dict[str, Any] = {
        "resource_uri": resource_id,
        "timespan": (
            f"{start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}/"
            f"{end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        ),
        "metricnames": ",".join(metric_names),
        "aggregation": aggregation,
        "interval": interval,
    }
    if metric_namespace:
        list_kwargs["metricnamespace"] = metric_namespace

    try:
        result = await asyncio.to_thread(
            monitor_client.metrics.list,
            **list_kwargs,
        )

        for metric in result.value:
            metric_entry: dict[str, Any] = {"unit": str(metric.unit)}
            timeseries_data: list[dict[str, Any]] = []
            for ts in metric.timeseries:
                for dp in ts.data:
                    if (
                        dp.average is not None
                        or dp.maximum is not None
                        or dp.minimum is not None
                        or dp.total is not None
                        or dp.count is not None
                    ):
                        timeseries_data.append({
                            "timestamp": dp.time_stamp.isoformat() if dp.time_stamp else "",
                            "average": round(dp.average, 2) if dp.average is not None else None,
                            "maximum": round(dp.maximum, 2) if dp.maximum is not None else None,
                            "minimum": round(dp.minimum, 2) if dp.minimum is not None else None,
                            "total": round(dp.total, 2) if dp.total is not None else None,
                            "count": round(dp.count, 2) if dp.count is not None else None,
                        })
            metric_entry["data"] = timeseries_data
            metrics_data[metric.name.value] = metric_entry

    except Exception as e:
        metrics_data["_error"] = f"Could not fetch metrics: {e}"

    return metrics_data


def _has_real_data(metrics_payload: dict[str, Any]) -> bool:
    """Return True when at least one metric has at least one data point."""
    for key, value in metrics_payload.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict) and value.get("data"):
            return True
    return False


async def _query_single_namespace(
    resource_id: str,
    subscription_id: str,
    token: str,
    metric_namespace: str | None,
    metric_names_override: list[str] | None,
    was_explicit: bool,
    start_dt: datetime,
    end_dt: datetime,
    interval: str,
    max_metrics: int,
) -> dict[str, Any]:
    """Query a single metric namespace and assemble a result block.

    Implements two robustness behaviours:
      * When the caller explicitly scoped to a namespace, return *all* metrics
        in that namespace (capped at ``max_metrics``) rather than the
        keyword-filtered top-N subset.
      * For child namespaces of the form ``<ParentType>/<childCollection>``,
        if the parent resource URI yields no data, transparently retry
        against the child resource URI (e.g.,
        ``<storageAccount>/blobServices/default``).
    """
    # 1. Resolve which metric names to ask for in this namespace.
    if metric_names_override:
        names_for_ns = metric_names_override
    else:
        names_for_ns = await _discover_metric_names(
            resource_id=resource_id,
            token=token,
            metric_namespace=metric_namespace,
            prioritize=not was_explicit,
            max_metrics=max_metrics,
        )

    if not names_for_ns:
        return {
            "_note": "No metrics discovered for this namespace",
            "metrics": {},
        }

    # 2. Try the parent resource URI first (with metricnamespace=).
    ns_metrics = await _get_resource_metrics(
        resource_id=resource_id,
        metric_names=names_for_ns,
        subscription_id=subscription_id,
        metric_namespace=metric_namespace,
        start_time=start_dt,
        end_time=end_dt,
        interval=interval,
    )

    used_resource_uri = resource_id

    # 3. Fallback: if the parent URI returned no real data for a sub-namespace,
    # retry against the conventional child URI (<parent>/<child>/default).
    if metric_namespace and not _has_real_data(ns_metrics):
        child_uri = _child_resource_uri_for_namespace(resource_id, metric_namespace)
        if child_uri:
            logger.debug(
                "Retrying namespace %s against child URI %s",
                metric_namespace,
                child_uri,
            )
            retry_metrics = await _get_resource_metrics(
                resource_id=child_uri,
                metric_names=names_for_ns,
                subscription_id=subscription_id,
                metric_namespace=metric_namespace,
                start_time=start_dt,
                end_time=end_dt,
                interval=interval,
            )
            if _has_real_data(retry_metrics):
                ns_metrics = retry_metrics
                used_resource_uri = child_uri

    return {
        "metrics_requested": names_for_ns,
        "queried_resource_id": used_resource_uri,
        "metrics": ns_metrics,
    }


async def get_utilization_metrics(
    resource_id: str,
    metric_names: list[str] | None = None,
    metric_namespace: str | None = None,
    metric_namespaces: list[str] | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    interval: str | None = None,
    subscription_id: str | None = None,
    include_child_namespaces: bool = False,
    include_custom_namespaces: bool = False,
    max_metrics_per_namespace: int = 20,
) -> str:
    """Fetch Azure Monitor metrics for a specific resource with full control.

    Supports child metric namespaces (e.g., Storage Account blob metrics live
    under ``Microsoft.Storage/storageAccounts/blobServices``) and a dynamic
    time window bounded by MAX_WINDOW_DAYS.

    Namespace selection rules (first match wins):
      1. ``metric_namespaces`` (plural) — explicit list of namespaces to query.
      2. ``metric_namespace`` (singular) — single explicit namespace.
      3. ``include_child_namespaces=True`` — auto-enumerate every namespace
         exposed by the resource via the metricNamespaces API. By default,
         only ``Platform`` namespaces are kept; set ``include_custom_namespaces``
         to True to also include ``Custom`` / ``Qos`` namespaces.
      4. Default — the resource's default namespace.

    For child namespaces that follow the ``<ParentType>/<childCollection>``
    convention, if querying the parent resource URI returns no metrics, this
    tool transparently retries against the child resource URI
    (``<parent>/<childCollection>/default``).

    Args:
        resource_id: Full ARM resource ID
            (e.g., ``/subscriptions/<sub>/resourceGroups/<rg>/providers/...``).
        metric_names: Specific metrics to fetch. When omitted and a namespace
            was explicitly specified, every metric in that namespace is
            returned (capped by ``max_metrics_per_namespace``). When omitted
            and no namespace was specified, top utilization metrics are
            auto-discovered by keyword scoring.
        metric_namespace: Single metric namespace, e.g.
            ``Microsoft.Storage/storageAccounts/blobServices``.
        metric_namespaces: Multiple namespaces to query in one call.
        start_time: ISO-8601 UTC start (e.g., ``2026-05-01T00:00:00Z``).
            Defaults to ``end_time - 3 days``.
        end_time: ISO-8601 UTC end. Defaults to now.
        interval: Time grain (e.g., ``PT5M``, ``PT1H``, ``PT12H``).
            Auto-selected from the window length when omitted.
        subscription_id: Subscription containing the resource. Defaults to the
            ``AZURE_SUBSCRIPTION_ID`` environment variable.
        include_child_namespaces: When True and no namespace was specified,
            enumerate all namespaces exposed by the resource and query each.
        include_custom_namespaces: When auto-enumerating, also include
            ``Custom`` / ``Qos`` namespaces (default: Platform only).
        max_metrics_per_namespace: Upper bound on metrics returned per
            namespace, to keep Azure Monitor query URLs within length limits.
    """
    try:
        validate_azure_resource_id(resource_id)
        sub_id = (
            validate_subscription_id(subscription_id)
            if subscription_id
            else get_subscription_id()
        )
        token = get_token()

        start_dt, end_dt = _resolve_time_window(start_time, end_time)
        chosen_interval = interval or _auto_interval(end_dt - start_dt)

        # ── Resolve which namespaces to query ────────────────────────────
        # Each entry is (namespace_or_None, classification_or_empty,
        # was_explicit). was_explicit=True means caller picked it, so we
        # should return all metrics rather than keyword-filtered subset.
        namespaces_to_query: list[tuple[str | None, str, bool]] = []

        if metric_namespaces:
            namespaces_to_query = [(ns, "", True) for ns in metric_namespaces if ns]
        elif metric_namespace:
            namespaces_to_query = [(metric_namespace, "", True)]
        elif include_child_namespaces:
            discovered = await _list_metric_namespaces(resource_id, token)
            if discovered:
                for entry in discovered:
                    cls = entry.get("classification", "")
                    if not include_custom_namespaces and cls and cls.lower() != "platform":
                        continue
                    namespaces_to_query.append((entry["name"], cls, False))
            if not namespaces_to_query:
                namespaces_to_query = [(None, "", False)]
        else:
            namespaces_to_query = [(None, "", False)]

        # ── Query each namespace, isolating per-namespace failures ───────
        results_by_namespace: dict[str, Any] = {}
        for ns, classification, was_explicit in namespaces_to_query:
            ns_key = ns or "(default)"
            try:
                ns_result = await _query_single_namespace(
                    resource_id=resource_id,
                    subscription_id=sub_id,
                    token=token,
                    metric_namespace=ns,
                    metric_names_override=metric_names,
                    was_explicit=was_explicit,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    interval=chosen_interval,
                    max_metrics=max_metrics_per_namespace,
                )
                if classification:
                    ns_result["classification"] = classification
                results_by_namespace[ns_key] = ns_result
            except Exception as ns_err:  # noqa: BLE001 — surface per-namespace
                logger.warning(
                    "namespace %s failed for %s: %s", ns_key, resource_id, ns_err
                )
                results_by_namespace[ns_key] = {
                    "_error": f"Namespace query failed: {ns_err}",
                    "classification": classification,
                }

        return success_response(
            {
                "resource_id": resource_id,
                "timespan": {
                    "start": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end": end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "interval": chosen_interval,
                },
                "namespaces": results_by_namespace,
            },
            scope=f"subscriptions/{sub_id}",
            extra_meta={
                "subscriptionId": sub_id,
                "namespacesQueried": len(namespaces_to_query),
            },
        )
    except ValueError as ve:
        return error_response(sanitize_error_message(str(ve)), code="400")
    except Exception as e:
        logger.exception("get_utilization_metrics failed")
        return error_response(sanitize_error_message(str(e)))
