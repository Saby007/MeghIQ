"""Azure Updates RSS feed parser.

Fetches and parses the official Azure Updates RSS feed to extract
structured update information including categories, status, and metadata.

Feed URL:
  https://www.microsoft.com/releasecommunications/api/v2/azure/rss
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

import httpx
import defusedxml.ElementTree as ET

from response import error_response, success_response
from tools.validators import sanitize_error_message

logger = logging.getLogger(__name__)

AZURE_UPDATES_RSS_URL = (
    "https://www.microsoft.com/releasecommunications/api/v2/azure/rss"
)

# Atom namespace used in the feed for <a10:updated>
ATOM_NS = "http://www.w3.org/2005/Atom"


def _parse_date(date_str: str) -> str | None:
    """Parse RSS date string to ISO format, or return None."""
    if not date_str:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    cleaned = date_str.strip()
    cleaned = re.sub(r"\s+Z$", " UTC", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)

    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.isoformat()
        except ValueError:
            continue
    return date_str.strip()


def _detect_status(title: str) -> str:
    """Detect the update status from the title prefix."""
    bracket_match = re.match(r"^\[(.+?)\]\s*", title)
    if bracket_match:
        return bracket_match.group(1).strip()

    colon_match = re.match(r"^(Retirement|Update|Announcement)\s*:", title, re.IGNORECASE)
    if colon_match:
        return colon_match.group(1).strip().capitalize()

    return "General"


def _clean_title(title: str) -> str:
    """Remove the status prefix from the title for cleaner display."""
    cleaned = re.sub(r"^\[.+?\]\s*", "", title)
    cleaned = re.sub(r"^(Retirement|Update|Announcement)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def normalize_category_tokens(category: str) -> set[str]:
    """Dynamically tokenize an RSS category for matching."""
    normalised = category.lower().strip()

    # Remove "azure" prefix
    normalised = re.sub(r"^azure\s+", "", normalised)

    # Extract parenthetical aliases
    aliases: list[str] = []
    paren_matches = re.findall(r"\(([^)]+)\)", normalised)
    for alias in paren_matches:
        aliases.append(alias.lower().strip())
    normalised = re.sub(r"\s*\([^)]*\)\s*", " ", normalised)

    words = re.findall(r"[a-z0-9]+", normalised)

    tokens: set[str] = set()
    tokens.update(words)
    tokens.update(aliases)

    for i in range(len(words) - 1):
        tokens.add(f"{words[i]} {words[i + 1]}")

    noise = {"and", "the", "of", "for", "a", "an", "in", "on", "to"}
    tokens -= noise

    return tokens


def _parse_feed_item(item: ET.Element) -> dict[str, Any]:
    """Parse a single RSS <item> element into a structured dict."""
    title_raw = (item.findtext("title") or "").strip()
    categories = [
        (cat.text or "").strip()
        for cat in item.findall("category")
        if cat.text
    ]

    meta_categories: list[str] = []
    service_categories: list[str] = []
    for cat in categories:
        cat_lower = cat.lower()
        if cat_lower in {
            "launched", "in preview", "in development",
            "retirements", "features", "services",
            "regions & datacenters", "pricing & offerings",
            "security", "compliance", "management",
            "sdk and tools", "open source", "operating system",
        }:
            meta_categories.append(cat)
        else:
            service_categories.append(cat)

    all_category_tokens: set[str] = set()
    for cat in service_categories:
        all_category_tokens |= normalize_category_tokens(cat)

    meta_tokens: set[str] = set()
    for cat in meta_categories:
        meta_tokens |= normalize_category_tokens(cat)

    status = _detect_status(title_raw)
    clean_title = _clean_title(title_raw)

    title_tokens = set(re.findall(r"[a-z0-9]+", clean_title.lower()))
    title_tokens -= {"now", "available", "generally", "public", "preview",
                     "new", "is", "are", "was", "with", "support",
                     "azure", "the", "for", "and", "in", "on", "to", "of", "a", "an"}

    return {
        "id": (item.findtext("guid") or "").strip(),
        "title": clean_title,
        "title_raw": title_raw,
        "status": status,
        "description": (item.findtext("description") or "").strip(),
        "link": (item.findtext("link") or "").strip(),
        "categories": categories,
        "service_categories": service_categories,
        "meta_categories": meta_categories,
        "published_date": _parse_date(item.findtext("pubDate") or ""),
        "updated_date": _parse_date(
            item.findtext(f"{{{ATOM_NS}}}updated") or ""
        ),
        "_category_tokens": all_category_tokens,
        "_meta_tokens": meta_tokens,
        "_title_tokens": title_tokens,
    }


async def _fetch_and_parse_feed() -> list[dict[str, Any]]:
    """Fetch the Azure Updates RSS feed and parse all items."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(AZURE_UPDATES_RSS_URL)

    if resp.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch Azure Updates RSS feed: {resp.status_code}"
        )

    root = ET.fromstring(resp.text)
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("Invalid RSS feed: no <channel> element found")

    items = channel.findall("item")
    return [_parse_feed_item(item) for item in items]


def _strip_internal_tokens(update: dict[str, Any]) -> dict[str, Any]:
    """Remove internal matching tokens before returning to user."""
    return {k: v for k, v in update.items() if not k.startswith("_")}


async def list_all_azure_updates(
    category: str | None = None,
    status: str | None = None,
    search: str | None = None,
    max_results: int = 50,
) -> str:
    """Fetch all Azure Updates from the official RSS feed with optional filtering."""
    try:
        updates = await _fetch_and_parse_feed()

        filtered = updates

        if category:
            cat_lower = category.lower()
            filtered = [
                u for u in filtered
                if any(cat_lower in c.lower() for c in u["categories"])
            ]

        if status:
            status_lower = status.lower()
            filtered = [
                u for u in filtered
                if status_lower in u["status"].lower()
            ]

        if search:
            search_lower = search.lower()
            filtered = [
                u for u in filtered
                if search_lower in u["title"].lower()
                or search_lower in u["description"].lower()
            ]

        filtered = filtered[:max_results]
        clean = [_strip_internal_tokens(u) for u in filtered]

        return success_response(
            clean,
            extra_meta={
                "totalUpdates": len(updates),
                "filteredCount": len(clean),
                "source": AZURE_UPDATES_RSS_URL,
            },
        )
    except Exception as e:
        logger.exception("list_all_azure_updates failed")
        return error_response(sanitize_error_message(str(e)))


async def get_azure_update_details(
    update_id: str,
) -> str:
    """Get full details for a specific Azure Update by its ID (GUID)."""
    try:
        updates = await _fetch_and_parse_feed()

        target = update_id.strip()
        match = next(
            (u for u in updates if u["id"] == target),
            None,
        )

        if match is None:
            return error_response(
                f"Update with ID '{update_id}' not found in the current feed.",
                code="NOT_FOUND",
            )

        return success_response(_strip_internal_tokens(match))
    except Exception as e:
        logger.exception("get_azure_update_details failed")
        return error_response(sanitize_error_message(str(e)))
