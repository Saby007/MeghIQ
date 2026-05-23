"""Azure Updates Intelligence — personalised, environment-aware update digest.

Combines resource discovery (Azure Resource Graph) with the Azure Updates
RSS feed to produce a categorised, relevance-scored digest of updates that
matter to a specific subscription's deployed resources.

The entire matching pipeline is dynamic — no hardcoded resource-to-category
mappings.  Resource types are tokenised algorithmically and compared against
RSS category tokens using set-overlap scoring with IDF weighting.

Two-phase approach:
  Phase 1 — get_personalized_updates(): compact, service-grouped executive summary
  Phase 2 — drill_down_updates(): expand any section, service, or status on demand
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from auth import get_subscription_id
from response import error_response, success_response
from tools.azure_updates import (
    _fetch_and_parse_feed,
    _strip_internal_tokens,
)
from tools.resource_discovery import (
    discover_deployed_resources,
    extract_resource_tokens,
)
from tools.validators import (
    sanitize_error_message,
    validate_output_directory,
    validate_subscription_id,
)

logger = logging.getLogger(__name__)


# ── Relevance Scoring ────────────────────────────────────────────────


def _compute_token_idf(all_updates: list[dict[str, Any]]) -> dict[str, float]:
    """Compute inverse document frequency for all tokens across updates."""
    doc_count = len(all_updates) or 1
    token_doc_freq: Counter[str] = Counter()

    for update in all_updates:
        unique_tokens = update.get("_category_tokens", set()) | update.get("_title_tokens", set())
        for token in unique_tokens:
            token_doc_freq[token] += 1

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
    """Score how relevant an update is to a resource type (0.0-1.0)."""
    if not resource_tokens:
        return 0.0

    update_all_tokens = update_category_tokens | update_title_tokens
    if not update_all_tokens:
        return 0.0

    overlap = resource_tokens & update_all_tokens

    if not overlap:
        for rt in resource_tokens:
            if " " in rt:
                for ut in update_all_tokens:
                    if rt in ut or ut in rt:
                        overlap.add(rt)
                        break

    if not overlap:
        return 0.0

    weighted_overlap = sum(idf_weights.get(t, 1.0) for t in overlap)
    weighted_total = sum(idf_weights.get(t, 1.0) for t in resource_tokens)

    if weighted_total == 0:
        return 0.0

    score = weighted_overlap / weighted_total
    return min(1.0, max(0.0, score))


# ── Urgency Scoring ──────────────────────────────────────────────────


def _compute_urgency(section_priority: int) -> float:
    """Derive urgency dynamically from the section's priority rank."""
    max_rank = max(_SECTION_PRIORITY.values())
    min_rank = min(_SECTION_PRIORITY.values())
    rank_range = max_rank - min_rank
    if rank_range == 0:
        return 0.5
    return 1.0 - ((section_priority - min_rank) / rank_range)


def _compute_priority_score(
    relevance: float,
    section_priority: int,
    urgency_weight: float = 0.4,
) -> float:
    """Combined score blending relevance and urgency."""
    urgency = _compute_urgency(section_priority)
    relevance_weight = 1.0 - urgency_weight
    return round(relevance * relevance_weight + urgency * urgency_weight, 3)


# ── Section Classification ───────────────────────────────────────────


def _derive_section_name(meta_categories: list[str], status: str) -> str:
    """Derive the section name from the feed's own meta-categories and status."""
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
    """Identify which deployed resource types are affected by an update."""
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

    affected.sort(key=lambda a: a["relevance_score"], reverse=True)
    return affected


# ── Service Grouping ─────────────────────────────────────────────────


def _derive_service_key(update: dict[str, Any]) -> str:
    """Derive a human-readable service key for grouping."""
    svc_cats = update.get("service_categories", [])
    if svc_cats:
        return svc_cats[0]
    return update.get("best_match_resource", "Other")


def _build_service_groups(
    updates: list[dict[str, Any]],
    highlights_per_group: int = 1,
) -> list[dict[str, Any]]:
    """Group updates by service and produce compact summaries."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for update in updates:
        key = _derive_service_key(update)
        groups[key].append(update)

    result: list[dict[str, Any]] = []

    for service_name, group_updates in groups.items():
        group_updates.sort(
            key=lambda u: u.get("priority_score", u.get("relevance_score", 0)),
            reverse=True,
        )

        status_breakdown: dict[str, int] = Counter()
        for u in group_updates:
            status_breakdown[u.get("status", "General")] += 1

        resource_types = [u.get("best_match_resource", "") for u in group_updates if u.get("best_match_resource")]
        best_resource_type = Counter(resource_types).most_common(1)[0][0] if resource_types else ""

        top_updates = [
            _strip_internal_tokens(u)
            for u in group_updates[:highlights_per_group]
        ]

        result.append({
            "service": service_name,
            "resource_type": best_resource_type,
            "update_count": len(group_updates),
            "status_breakdown": dict(status_breakdown),
            "max_relevance": max(u.get("relevance_score", 0) for u in group_updates),
            "max_priority_score": max(u.get("priority_score", 0) for u in group_updates),
            "total_affected_resources": sum(u.get("total_affected_count", 0) for u in group_updates),
            "top_updates": top_updates,
        })

    result.sort(key=lambda g: g["max_priority_score"], reverse=True)
    return result


# ── CSV Export ────────────────────────────────────────────────────────

_CSV_COLUMNS = [
    "ID", "Title", "Status", "Section", "Priority", "Service Group",
    "Urgency Score", "Priority Score", "Published Date", "Updated Date",
    "Relevance Score", "Best Match Resource", "Total Affected Resources",
    "Service Categories", "Link", "Description",
]


def _export_updates_csv(
    relevant_updates: list[dict[str, Any]],
    output_dir: str | None = None,
) -> str:
    """Export all relevant updates to a CSV file."""
    if output_dir:
        out = Path(validate_output_directory(output_dir))
    else:
        out = Path.cwd()
    out.mkdir(parents=True, exist_ok=True)

    csv_path = out / "azure_updates_report.csv"

    sorted_updates = sorted(
        relevant_updates,
        key=lambda u: (
            _SECTION_PRIORITY.get(u.get("_section", "Other Updates"), 50),
            -(u.get("priority_score", u.get("relevance_score", 0))),
        ),
    )

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()

        for u in sorted_updates:
            section = u.get("_section", "Other Updates")
            svc_cats = u.get("service_categories", [])
            section_pri = _SECTION_PRIORITY.get(section, 50)

            writer.writerow({
                "ID": u.get("id", ""),
                "Title": u.get("title", ""),
                "Status": u.get("status", ""),
                "Section": section,
                "Priority": section_pri,
                "Service Group": _derive_service_key(u),
                "Urgency Score": round(_compute_urgency(section_pri), 3),
                "Priority Score": u.get("priority_score", 0),
                "Published Date": u.get("published_date", ""),
                "Updated Date": u.get("updated_date", ""),
                "Relevance Score": u.get("relevance_score", 0),
                "Best Match Resource": u.get("best_match_resource", ""),
                "Total Affected Resources": u.get("total_affected_count", 0),
                "Service Categories": "; ".join(svc_cats) if svc_cats else "",
                "Link": u.get("link", ""),
                "Description": (u.get("description", "") or "")[:300],
            })

    logger.info("Exported %d updates to %s", len(sorted_updates), csv_path)
    return str(csv_path.resolve())


# ── Core Scoring Pipeline ────────────────────────────────────────────


async def _run_scoring_pipeline(
    subscription_id: str | None = None,
    urgency_weight: float = 0.4,
) -> dict[str, Any]:
    """Run the full discovery -> fetch -> score -> classify pipeline."""
    sub_id = (
        validate_subscription_id(subscription_id)
        if subscription_id
        else get_subscription_id()
    )

    # Step 1: Discover deployed resources
    discovery_result_json = await discover_deployed_resources(sub_id)
    discovery_result = json.loads(discovery_result_json)

    if discovery_result.get("status") != "success":
        raise RuntimeError(
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

        if max_relevance > 0.15:
            update_enriched = dict(update)
            update_enriched["relevance_score"] = round(max_relevance, 3)
            update_enriched["best_match_resource"] = best_match_type

            update_enriched["affected_resources"] = _assess_impact(
                update, type_summary, resource_tokens_by_type, idf_weights,
            )
            update_enriched["total_affected_count"] = sum(
                a["resource_count"] for a in update_enriched["affected_resources"]
            )

            relevant_updates.append(update_enriched)

    # Step 5: Classify into sections and compute priority scores
    sections_map: dict[str, list[dict[str, Any]]] = {}

    for update in relevant_updates:
        section = _derive_section_name(
            update.get("meta_categories", []),
            update.get("status", ""),
        )
        update["_section"] = section

        section_pri = _SECTION_PRIORITY.get(section, 50)
        update["priority_score"] = _compute_priority_score(
            update["relevance_score"], section_pri, urgency_weight,
        )

        if section not in sections_map:
            sections_map[section] = []
        sections_map[section].append(update)

    return {
        "sub_id": sub_id,
        "type_summary": type_summary,
        "total_resources": total_resources,
        "unique_types": unique_types,
        "all_updates": all_updates,
        "relevant_updates": relevant_updates,
        "sections_map": sections_map,
    }


# ── Main Orchestrator (Phase 1) ─────────────────────────────────────


async def get_personalized_updates(
    subscription_id: str | None = None,
    highlights_per_section: int = 3,
    highlights_per_group: int = 1,
    urgency_weight: float = 0.4,
    export_csv: bool = True,
    csv_output_dir: str | None = None,
) -> str:
    """Get personalised Azure Updates digest based on deployed resources.

    Returns a compact, service-grouped executive summary that represents
    ALL relevant updates. Use drill_down_updates() to expand specific areas.
    """
    try:
        pipeline = await _run_scoring_pipeline(subscription_id, urgency_weight)

        sub_id = pipeline["sub_id"]
        type_summary = pipeline["type_summary"]
        total_resources = pipeline["total_resources"]
        unique_types = pipeline["unique_types"]
        all_updates = pipeline["all_updates"]
        relevant_updates = pipeline["relevant_updates"]
        sections_map = pipeline["sections_map"]

        csv_file_path: str | None = None
        if export_csv:
            try:
                csv_file_path = _export_updates_csv(
                    relevant_updates, output_dir=csv_output_dir,
                )
            except Exception:
                logger.exception("Failed to export updates CSV")

        sections_output: list[dict[str, Any]] = []

        for section_name, updates in sorted(
            sections_map.items(),
            key=lambda x: _SECTION_PRIORITY.get(x[0], 50),
        ):
            updates.sort(
                key=lambda u: u.get("priority_score", 0),
                reverse=True,
            )

            critical_highlights = [
                _strip_internal_tokens(u)
                for u in updates[:highlights_per_section]
            ]

            service_groups = _build_service_groups(updates, highlights_per_group)

            sections_output.append({
                "section": section_name,
                "priority": _SECTION_PRIORITY.get(section_name, 50),
                "total_count": len(updates),
                "service_groups": service_groups,
                "critical_highlights": critical_highlights,
            })

        all_relevant_sorted = sorted(
            relevant_updates,
            key=lambda u: u.get("priority_score", 0),
            reverse=True,
        )

        digest_highlight_count = max(5, min(15, len(relevant_updates) // 20))
        digest_highlights = [
            _strip_internal_tokens(u)
            for u in all_relevant_sorted[:digest_highlight_count]
        ]

        top_services = [ts["service_name"] for ts in type_summary[:10]]

        extra: dict[str, Any] = {
            "highlightsPerSection": highlights_per_section,
            "highlightsPerGroup": highlights_per_group,
            "urgencyWeight": urgency_weight,
            "relevanceThreshold": 0.15,
        }
        if csv_file_path:
            extra["csv_file_path"] = csv_file_path
            extra["csv_note"] = (
                f"All {len(relevant_updates)} relevant updates have been "
                f"exported to the CSV file above."
            )
        extra["drill_down_hint"] = (
            "To see full details for any section, service, or status, "
            "use the drill_down_azure_updates tool with "
            "section='...' or service='...' or status='...'."
        )

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
                        s["total_count"] for s in sections_output
                        if s["priority"] <= 2
                    ),
                },
                "digest_highlights": digest_highlights,
                "sections": sections_output,
            },
            scope=f"subscriptions/{sub_id}",
            extra_meta=extra,
        )
    except ValueError as ve:
        return error_response(sanitize_error_message(str(ve)), code="400")
    except Exception as e:
        logger.exception("get_personalized_updates failed")
        return error_response(sanitize_error_message(str(e)))


# ── Drill-Down (Phase 2) ────────────────────────────────────────────


async def drill_down_updates(
    subscription_id: str | None = None,
    section: str | None = None,
    service: str | None = None,
    status: str | None = None,
    min_relevance: float = 0.15,
    max_results: int = 25,
    urgency_weight: float = 0.4,
) -> str:
    """Drill down into a specific slice of the personalised updates digest.

    Supports filtering by section name, service name, and/or status.
    All filters are case-insensitive partial matches combined with AND logic.
    """
    try:
        pipeline = await _run_scoring_pipeline(subscription_id, urgency_weight)

        sub_id = pipeline["sub_id"]
        relevant_updates = pipeline["relevant_updates"]

        filtered = relevant_updates

        if section:
            section_lower = section.lower()
            filtered = [
                u for u in filtered
                if section_lower in u.get("_section", "").lower()
            ]

        if service:
            service_lower = service.lower()
            filtered = [
                u for u in filtered
                if any(service_lower in sc.lower() for sc in u.get("service_categories", []))
                or service_lower in (u.get("best_match_resource") or "").lower()
                or service_lower in _derive_service_key(u).lower()
            ]

        if status:
            status_lower = status.lower()
            filtered = [
                u for u in filtered
                if status_lower in u.get("status", "").lower()
            ]

        if min_relevance > 0:
            filtered = [
                u for u in filtered
                if u.get("relevance_score", 0) >= min_relevance
            ]

        filtered.sort(
            key=lambda u: u.get("priority_score", 0),
            reverse=True,
        )

        total_matching = len(filtered)
        filtered = filtered[:max_results]

        clean_updates = [_strip_internal_tokens(u) for u in filtered]

        applied_filters: dict[str, str] = {}
        if section:
            applied_filters["section"] = section
        if service:
            applied_filters["service"] = service
        if status:
            applied_filters["status"] = status
        if min_relevance > 0.15:
            applied_filters["min_relevance"] = str(min_relevance)

        return success_response(
            {
                "filters_applied": applied_filters,
                "total_matching": total_matching,
                "returned": len(clean_updates),
                "updates": clean_updates,
            },
            scope=f"subscriptions/{sub_id}",
            extra_meta={
                "maxResults": max_results,
                "urgencyWeight": urgency_weight,
                "note": (
                    f"Showing {len(clean_updates)} of {total_matching} "
                    f"matching updates. Adjust max_results to see more."
                    if total_matching > len(clean_updates)
                    else f"All {total_matching} matching updates shown."
                ),
            },
        )
    except ValueError as ve:
        return error_response(sanitize_error_message(str(ve)), code="400")
    except Exception as e:
        logger.exception("drill_down_updates failed")
        return error_response(sanitize_error_message(str(e)))
