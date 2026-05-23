"""Azure Updates Historical Search — paginated OData API fetcher.

The standard RSS feed only returns ~200 recent updates (~4 months).
This module uses the Microsoft Release Communications OData REST API
with server-side filtering and pagination to retrieve Azure Updates
dating back up to 3 years.

API Base: https://www.microsoft.com/releasecommunications/api/v2/azure
Supports: $top, $skip, $count, $filter (OData v4)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx

from response import error_response, success_response
from tools.validators import sanitize_error_message

logger = logging.getLogger(__name__)

ODATA_API_URL = "https://www.microsoft.com/releasecommunications/api/v2/azure"

# Maximum items per page (API limit)
_PAGE_SIZE = 100
# Hard ceiling to avoid runaway pagination
_MAX_PAGES = 50
# Maximum lookback in years
_MAX_YEARS = 3


def _parse_api_date(date_str: str) -> datetime | None:
    """Parse date strings from the API (ISO 8601 with optional fractional seconds)."""
    if not date_str:
        return None
    cleaned = date_str.strip()
    # Strip fractional seconds (e.g. '.5936893Z' -> 'Z')
    cleaned = re.sub(r"\.\d+Z$", "Z", cleaned)
    cleaned = re.sub(r"\.\d+$", "", cleaned)
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%m/%d/%Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _normalise_item(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw OData item into the standard update schema."""
    created = _parse_api_date(item.get("created", ""))
    modified = _parse_api_date(item.get("modified", ""))

    title_raw = (item.get("title") or "").strip()
    # Strip HTML tags from description
    desc_raw = item.get("description") or ""
    description = re.sub(r"<[^>]+>", " ", desc_raw)
    description = re.sub(r"\s+", " ", description).strip()

    status = (item.get("status") or "General").strip()

    products = item.get("products") or []
    product_categories = item.get("productCategories") or []
    tags = item.get("tags") or []

    ga_date = item.get("generalAvailabilityDate") or ""
    preview_date = item.get("previewAvailabilityDate") or ""

    return {
        "id": (item.get("id") or "").strip(),
        "title": title_raw,
        "status": status,
        "description": description[:500] if len(description) > 500 else description,
        "products": products,
        "product_categories": product_categories,
        "tags": tags,
        "published_date": created.isoformat() if created else None,
        "updated_date": modified.isoformat() if modified else None,
        "ga_date": ga_date,
        "preview_date": preview_date,
    }


def _build_filter_clauses(
    *,
    product: str | None = None,
    category: str | None = None,
    status: str | None = None,
) -> str | None:
    """Build an OData $filter string from user parameters.

    The API stores lifecycle status in both the ``status`` field
    (e.g. 'Launched', 'In preview') and the ``tags`` collection
    (e.g. 'Retirements', 'Features').  We generate a disjunction
    so that either location matches.
    """
    clauses: list[str] = []

    if product:
        escaped = product.replace("'", "''")
        clauses.append(f"products/any(p: p eq '{escaped}')")

    if category:
        escaped = category.replace("'", "''")
        clauses.append(f"productCategories/any(c: c eq '{escaped}')")

    if status:
        escaped = status.replace("'", "''")
        # Map common user-friendly names to API values for tags
        tag_map: dict[str, str] = {
            "retirement": "Retirements",
            "retirements": "Retirements",
            "features": "Features",
            "security": "Security",
            "compliance": "Compliance",
            "services": "Services",
            "regions & datacenters": "Regions & Datacenters",
            "pricing & offerings": "Pricing & Offerings",
        }
        tag_value = tag_map.get(escaped.lower())
        if tag_value:
            tag_escaped = tag_value.replace("'", "''")
            clauses.append(
                f"(status eq '{escaped}' or tags/any(t: t eq '{tag_escaped}'))"
            )
        else:
            clauses.append(f"status eq '{escaped}'")

    return " and ".join(clauses) if clauses else None


def _matches_search(item: dict[str, Any], search_lower: str) -> bool:
    """Client-side keyword search across title and description."""
    return (
        search_lower in (item.get("title") or "").lower()
        or search_lower in (item.get("description") or "").lower()
    )


def _within_date_range(
    item: dict[str, Any],
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> bool:
    """Check if an item falls within the date range."""
    pub = _parse_api_date(item.get("created", ""))
    if pub is None:
        return True  # include items without dates
    if from_dt and pub < from_dt:
        return False
    if to_dt and pub > to_dt:
        return False
    return True


async def search_azure_updates_history(
    product: str | None = None,
    category: str | None = None,
    status: str | None = None,
    search: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    max_results: int = 100,
) -> str:
    """Search Azure Updates history via the OData API with pagination.

    Retrieves updates from the Microsoft Release Communications API,
    supporting server-side filtering by product, category, and status,
    plus client-side keyword search and date range filtering.

    Can return data going back up to 3 years.

    Args:
        product: Filter by product name (e.g. 'Virtual Machines', 'Azure Kubernetes Service (AKS)').
                 Must be an exact match to the API's product taxonomy.
        category: Filter by product category (e.g. 'Compute', 'Databases', 'Networking').
                  Must be an exact match.
        status: Filter by status (e.g. 'Launched', 'In preview', 'Retirement', 'In development').
        search: Keyword search across title and description (client-side, case-insensitive).
        from_date: Start date in YYYY-MM-DD format. Defaults to 3 years ago.
        to_date: End date in YYYY-MM-DD format. Defaults to today.
        max_results: Maximum number of results to return (default 100, max 500).

    Returns:
        JSON string with matching updates sorted by date (newest first).
    """
    try:
        max_results = min(max(1, max_results), 500)

        # Parse date range
        now = datetime.now(timezone.utc)
        if to_date:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc,
            )
        else:
            to_dt = now

        if from_date:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            from_dt = now - timedelta(days=_MAX_YEARS * 365)

        # Clamp to max 3 years
        earliest_allowed = now - timedelta(days=_MAX_YEARS * 365)
        if from_dt < earliest_allowed:
            from_dt = earliest_allowed

        # Build OData filter
        odata_filter = _build_filter_clauses(
            product=product,
            category=category,
            status=status,
        )

        # Fetch pages
        all_items: list[dict[str, Any]] = []
        skip = 0
        search_lower = search.lower().strip() if search else None

        async with httpx.AsyncClient(timeout=30.0) as client:
            for _ in range(_MAX_PAGES):
                params: dict[str, str] = {
                    "$top": str(_PAGE_SIZE),
                    "$skip": str(skip),
                    "$count": "true",
                }
                if odata_filter:
                    params["$filter"] = odata_filter

                resp = await client.get(
                    ODATA_API_URL,
                    params=params,
                    headers={"Accept": "application/json"},
                )

                if resp.status_code != 200:
                    logger.warning("OData API returned %d at skip=%d", resp.status_code, skip)
                    break

                data = resp.json()
                page_items = data.get("value", [])
                total_count = data.get("@odata.count")

                if not page_items:
                    break

                for raw_item in page_items:
                    if not _within_date_range(raw_item, from_dt, to_dt):
                        continue
                    if search_lower and not _matches_search(raw_item, search_lower):
                        continue
                    all_items.append(raw_item)

                skip += _PAGE_SIZE
                if total_count and skip >= total_count:
                    break

        # Normalise and sort by date (newest first)
        normalised = [_normalise_item(item) for item in all_items]
        normalised.sort(
            key=lambda x: x.get("published_date") or "",
            reverse=True,
        )

        # Apply max_results after sorting
        trimmed = normalised[:max_results]

        return success_response(
            trimmed,
            extra_meta={
                "totalAvailable": total_count if total_count else "unknown",
                "matchedInDateRange": len(normalised),
                "returned": len(trimmed),
                "dateRange": {
                    "from": from_dt.strftime("%Y-%m-%d"),
                    "to": to_dt.strftime("%Y-%m-%d"),
                },
                "filters": {
                    "product": product,
                    "category": category,
                    "status": status,
                    "search": search,
                },
                "source": ODATA_API_URL,
            },
        )

    except ValueError as e:
        return error_response(sanitize_error_message(f"Invalid parameter: {e}"))
    except Exception as e:
        logger.exception("search_azure_updates_history failed")
        return error_response(sanitize_error_message(str(e)))
