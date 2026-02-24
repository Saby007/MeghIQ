"""Azure Updates Intelligence — personalised, environment-aware update digest.

Combines resource discovery (Azure Resource Graph) with the Azure Updates
RSS feed to produce a categorised, relevance-scored digest of updates that
matter to a specific subscription's deployed resources.

The entire matching pipeline is dynamic — no hardcoded resource-to-category
mappings.  Resource types are tokenised algorithmically and compared against
RSS category tokens using set-overlap scoring.

Sections are derived from the feed's own meta-category taxonomy (e.g.
"Retirements", "Security", "Pricing & Offerings", "Features").
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Any

from azure_cost_mcp.auth import get_subscription_id
from azure_cost_mcp.response import error_response, success_response
from azure_cost_mcp.tools.azure_updates import (
    _fetch_and_parse_feed,
    _strip_internal_tokens,
)
from azure_cost_mcp.tools.resource_discovery import (
    discover_deployed_resources,
    extract_resource_tokens,
)

logger = logging.getLogger(__name__)


# ── Relevance Scoring ────────────────────────────────────────────────


def _compute_token_idf(all_updates: list[dict[str, Any]]) -> dict[str, float]:
    """Compute inverse document frequency for all tokens across updates.

    Tokens that appear in many updates (e.g. "compute") get lower weight.
    Tokens that are rare (e.g. "postgresql") get higher weight.
    This is computed dynamically from the actual feed content.
    """
    doc_count = len(all_updates) or 1
    token_doc_freq: Counter[str] = Counter()

    for update in all_updates:
        # Each update's unique tokens
        unique_tokens = update.get("_category_tokens", set()) | update.get("_title_tokens", set())
        for token in unique_tokens:
            token_doc_freq[token] += 1

    # IDF = log(N / df) but simplified to N / df for weighting
    idf: dict[str, float] = {}
    for token, df in token_doc_freq.items():
        idf[token] = doc_count / df

    return idf


def _compute_relevance(
    resource_tokens: set[str],
    update_category_tokens: set[str],
    update_title_tokens: set[str],
    idf_weights: dict[str, float],
) -> float:
    """Score how relevant an update is to a resource type (0.0–1.0).

    Uses weighted token overlap:
    - Tokens shared between resource and update are identified
    - Each shared token is weighted by its IDF (rarer tokens count more)
    - Score is normalised to 0.0–1.0 range
    """
    if not resource_tokens:
        return 0.0

    update_all_tokens = update_category_tokens | update_title_tokens

    if not update_all_tokens:
        return 0.0

    # Find overlapping tokens
    overlap = resource_tokens & update_all_tokens

    if not overlap:
        # Try substring matching for compound tokens
        # e.g. resource token "virtual machines" found within update token "virtual machines"
        for rt in resource_tokens:
            if " " in rt:  # compound token
                for ut in update_all_tokens:
                    if rt in ut or ut in rt:
                        overlap.add(rt)
                        break

    if not overlap:
        return 0.0

    # Weighted score using IDF
    weighted_overlap = sum(idf_weights.get(t, 1.0) for t in overlap)
    weighted_total = sum(idf_weights.get(t, 1.0) for t in resource_tokens)

    if weighted_total == 0:
        return 0.0

    score = weighted_overlap / weighted_total

    # Clamp to 0.0–1.0
    return min(1.0, max(0.0, score))


# ── Section Classification ───────────────────────────────────────────


def _derive_section_name(meta_categories: list[str], status: str) -> str:
    """Derive the section name from the feed's own meta-categories and status.

    Priority logic (first match wins):
    1. If meta-categories contain "Retirements" → "Action Required: Retirements & Deprecations"
    2. If meta-categories contain "Security" or "Compliance" → "Security & Compliance Updates"
    3. If meta-categories contain "Pricing & Offerings" → "Cost & Pricing Updates"
    4. If meta-categories contain "Regions & Datacenters" → "Regional Expansion"
    5. If status indicates "In preview" or "In development" → "Preview & Upcoming Features"
    6. If status is "Launched" or meta has "Features" → "New Features & GA Announcements"
    7. Fallback → "Other Updates"

    The section names are derived from what the feed provides — the feed's own tags
    drive the classification.
    """
    meta_lower = {m.lower() for m in meta_categories}
    status_lower = status.lower()

    if "retirements" in meta_lower:
        return "Action Required: Retirements & Deprecations"

    if "security" in meta_lower or "compliance" in meta_lower:
        return "Security & Compliance Updates"

    if "pricing & offerings" in meta_lower:
        return "Cost & Pricing Updates"

    if "regions & datacenters" in meta_lower:
        return "Regional Expansion"

    if status_lower in ("in preview", "in development"):
        return "Preview & Upcoming Features"

    if status_lower == "launched" or "features" in meta_lower:
        return "New Features & GA Announcements"

    return "Other Updates"


# Section priority — derived from urgency of action required.
# Lower number = shown first.
_SECTION_PRIORITY = {
    "Action Required: Retirements & Deprecations": 1,
    "Security & Compliance Updates": 2,
    "Cost & Pricing Updates": 3,
    "New Features & GA Announcements": 4,
    "Preview & Upcoming Features": 5,
    "Regional Expansion": 6,
    "Other Updates": 99,
}


# ── Impact Assessment ────────────────────────────────────────────────


def _assess_impact(
    update: dict[str, Any],
    type_summary: list[dict[str, Any]],
    resource_tokens_by_type: dict[str, set[str]],
    idf_weights: dict[str, float],
) -> list[dict[str, Any]]:
    """Identify which deployed resource types are affected by an update.

    Returns a list of affected resource types with their counts.
    """
    affected: list[dict[str, Any]] = []

    update_cat_tokens = update.get("_category_tokens", set())
    update_title_tokens = update.get("_title_tokens", set())

    for type_info in type_summary:
        rtype = type_info["type"]
        tokens = resource_tokens_by_type.get(rtype, set())

        relevance = _compute_relevance(
            tokens, update_cat_tokens, update_title_tokens, idf_weights,
        )

        if relevance > 0.2:
            affected.append({
                "resource_type": rtype,
                "service_name": type_info.get("service_name", rtype),
                "resource_count": type_info.get("total_count", 0),
                "locations": type_info.get("locations", []),
                "relevance_score": round(relevance, 3),
            })

    # Sort by relevance
    affected.sort(key=lambda a: a["relevance_score"], reverse=True)
    return affected


# ── Main Orchestrator ────────────────────────────────────────────────


async def get_personalized_updates(
    subscription_id: str | None = None,
    max_per_section: int = 10,
) -> str:
    """Get personalised Azure Updates digest based on deployed resources.

    Discovers resources in the subscription via Azure Resource Graph,
    fetches the Azure Updates RSS feed, scores each update for relevance,
    classifies into sections, and returns a structured digest.

    Args:
        subscription_id: Azure subscription ID (defaults to AZURE_SUBSCRIPTION_ID env var).
        max_per_section: Maximum number of updates per section (default 10).

    Returns:
        JSON with subscription summary, sections (ordered by priority),
        and relevance-scored updates per section.
    """
    try:
        sub_id = subscription_id or get_subscription_id()

        # Step 1: Discover deployed resources
        discovery_result_json = await discover_deployed_resources(sub_id)
        discovery_result = json.loads(discovery_result_json)

        if discovery_result.get("status") != "success":
            return error_response(
                "Failed to discover deployed resources: "
                + discovery_result.get("error", {}).get("message", "Unknown error")
            )

        type_summary = discovery_result["data"]["type_summary"]
        total_resources = discovery_result["metadata"]["totalResources"]
        unique_types = discovery_result["metadata"]["uniqueResourceTypes"]

        # Build token sets per resource type
        resource_tokens_by_type: dict[str, set[str]] = {}
        all_resource_tokens: set[str] = set()
        for ts in type_summary:
            tokens = set(ts["tokens"])
            resource_tokens_by_type[ts["type"]] = tokens
            all_resource_tokens |= tokens

        # Step 2: Fetch Azure Updates
        all_updates = await _fetch_and_parse_feed()

        # Step 3: Compute IDF weights dynamically from the feed
        idf_weights = _compute_token_idf(all_updates)

        # Step 4: Score and filter updates relevant to deployed resources
        relevant_updates: list[dict[str, Any]] = []

        for update in all_updates:
            cat_tokens = update.get("_category_tokens", set())
            title_tokens = update.get("_title_tokens", set())

            # Compute max relevance across all deployed resource types
            max_relevance = 0.0
            best_match_type = None

            for ts in type_summary:
                tokens = resource_tokens_by_type[ts["type"]]
                score = _compute_relevance(
                    tokens, cat_tokens, title_tokens, idf_weights,
                )
                if score > max_relevance:
                    max_relevance = score
                    best_match_type = ts["type"]

            if max_relevance > 0.15:  # Relevance threshold
                update_enriched = dict(update)
                update_enriched["relevance_score"] = round(max_relevance, 3)
                update_enriched["best_match_resource"] = best_match_type

                # Assess impact — which resource types are affected
                update_enriched["affected_resources"] = _assess_impact(
                    update, type_summary, resource_tokens_by_type, idf_weights,
                )

                # Total affected resource count
                update_enriched["total_affected_count"] = sum(
                    a["resource_count"] for a in update_enriched["affected_resources"]
                )

                relevant_updates.append(update_enriched)

        # Step 5: Classify into sections
        sections_map: dict[str, list[dict[str, Any]]] = {}

        for update in relevant_updates:
            section = _derive_section_name(
                update.get("meta_categories", []),
                update.get("status", ""),
            )
            if section not in sections_map:
                sections_map[section] = []
            sections_map[section].append(update)

        # Sort within each section by relevance, limit per section
        for section_name in sections_map:
            sections_map[section_name].sort(
                key=lambda u: u.get("relevance_score", 0),
                reverse=True,
            )
            sections_map[section_name] = sections_map[section_name][:max_per_section]

        # Build output sections ordered by priority
        sections_output: list[dict[str, Any]] = []
        for section_name, updates in sorted(
            sections_map.items(),
            key=lambda x: _SECTION_PRIORITY.get(x[0], 50),
        ):
            clean_updates = []
            for u in updates:
                clean = _strip_internal_tokens(u)
                clean_updates.append(clean)

            sections_output.append({
                "section": section_name,
                "priority": _SECTION_PRIORITY.get(section_name, 50),
                "count": len(clean_updates),
                "updates": clean_updates,
            })

        # Build subscription summary
        top_services = [
            ts["service_name"]
            for ts in type_summary[:10]
        ]

        return success_response(
            {
                "subscription_summary": {
                    "subscription_id": sub_id,
                    "total_resources": total_resources,
                    "unique_resource_types": unique_types,
                    "top_services": top_services,
                },
                "digest_summary": {
                    "total_feed_updates": len(all_updates),
                    "relevant_updates": len(relevant_updates),
                    "sections": len(sections_output),
                    "action_required": sum(
                        s["count"] for s in sections_output
                        if s["priority"] <= 2
                    ),
                },
                "sections": sections_output,
            },
            scope=f"subscriptions/{sub_id}",
            extra_meta={
                "maxPerSection": max_per_section,
                "relevanceThreshold": 0.15,
            },
        )
    except Exception as e:
        logger.exception("get_personalized_updates failed")
        return error_response(str(e))
