"""PDF Report Generator for Azure Updates Intelligence.

Produces a professional, colour-coded PDF report using fpdf2.

Report structure:
  - Cover page with subscription summary and generation date
  - Executive summary with key metrics and section overview
  - Per-section pages with service-grouped updates
  - Critical highlights per section shown first, then service group summaries
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any

from response import error_response, success_response
from tools.update_intelligence import get_personalized_updates
from tools.validators import sanitize_error_message, validate_output_path

logger = logging.getLogger(__name__)

# Colour palette by priority rank
_PRIORITY_COLORS = {
    1: (220, 53, 69),     # Red — Retirements / Action Required
    2: (255, 140, 0),     # Orange — Security
    3: (40, 167, 69),     # Green — Cost / Pricing
    4: (0, 123, 255),     # Blue — New features / GA
    5: (111, 66, 193),    # Purple — Preview / Upcoming
    6: (23, 162, 184),    # Teal — Regional Expansion
    99: (108, 117, 125),  # Grey — Other
}


def _get_section_color(priority: int) -> tuple[int, int, int]:
    return _PRIORITY_COLORS.get(priority, _PRIORITY_COLORS[99])


def _sanitize_text(text: str) -> str:
    """Replace Unicode characters unsupported by Helvetica with ASCII equivalents."""
    replacements = {
        "\u2014": "--", "\u2013": "-", "\u2011": "-",
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2026": "...", "\u00a0": " ", "\u202f": " ",
        "\u00b7": "-", "\u2022": "-", "\u2192": "->", "\u2190": "<-",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _truncate(text: str, max_len: int = 120) -> str:
    text = _sanitize_text(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _render_update_item(
    pdf: Any,
    update: dict[str, Any],
    index: int,
    color: tuple[int, int, int],
    section_name: str,
) -> None:
    """Render a single update item in the PDF."""
    if pdf.get_y() > 245:
        pdf.add_page()
        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, _sanitize_text(f"  {section_name} (continued)"), fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    title = update.get("title", "Untitled")
    status = update.get("status", "Unknown")
    relevance = update.get("relevance_score", 0)
    priority_score = update.get("priority_score", 0)
    link = update.get("link", "")
    affected = update.get("affected_resources", [])
    total_affected = update.get("total_affected_count", 0)
    services = update.get("service_categories", [])

    pdf.set_text_color(30, 30, 30)
    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(0, 6, _sanitize_text(f"{index}. {_truncate(title, 150)}"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)

    meta_parts = [f"Status: {status}"]
    if relevance:
        meta_parts.append(f"Relevance: {relevance:.1%}")
    if priority_score:
        meta_parts.append(f"Priority: {priority_score:.1%}")
    if total_affected:
        meta_parts.append(f"Affected resources: {total_affected}")
    if services:
        meta_parts.append(f"Services: {', '.join(services[:3])}")

    pdf.cell(0, 5, _sanitize_text("   ".join(meta_parts)), new_x="LMARGIN", new_y="NEXT")

    if affected:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(80, 80, 80)
        for ar in affected[:3]:
            svc_name = ar.get("service_name", ar.get("resource_type", ""))
            rc = ar.get("resource_count", 0)
            locs = ", ".join(ar.get("locations", [])[:3])
            pdf.cell(
                0, 4,
                _sanitize_text(f"      {svc_name} ({rc} resources) -- {locs}"),
                new_x="LMARGIN", new_y="NEXT",
            )

    if link:
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(0, 102, 204)
        pdf.cell(0, 5, f"   {_truncate(link, 100)}", link=link, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(3)


def _build_pdf(
    digest: dict[str, Any],
    report_type: str = "full",
) -> bytes:
    """Build the PDF document and return the raw bytes."""
    from fpdf import FPDF

    class AzureUpdatesPDF(FPDF):
        def header(self):
            if self.page_no() > 1:
                self.set_font("Helvetica", "I", 8)
                self.set_text_color(108, 117, 125)
                self.cell(0, 6, "Azure Updates Intelligence Report", align="L")
                self.cell(0, 6, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
                self.line(10, 16, 200, 16)
                self.ln(4)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, "Generated by MeghIQ MCP Server", align="C")

    pdf = AzureUpdatesPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(15, 15, 15)

    sub_summary = digest.get("subscription_summary", {})
    dig_summary = digest.get("digest_summary", {})
    sections = digest.get("sections", [])
    digest_highlights = digest.get("digest_highlights", [])

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Cover Page
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(0, 102, 204)
    pdf.ln(40)
    pdf.cell(0, 15, "Azure Updates", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 20)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 12, "Intelligence Report", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(10)
    pdf.set_draw_color(0, 102, 204)
    pdf.set_line_width(0.8)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(12)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(80, 80, 80)
    sub_id = sub_summary.get("subscription_id", "N/A")
    pdf.cell(0, 7, _sanitize_text(f"Subscription: {sub_id}"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0, 7,
        _sanitize_text(
            f"Resources: {sub_summary.get('total_resources', 0)} across "
            f"{sub_summary.get('unique_resource_types', 0)} resource types"
        ),
        align="C", new_x="LMARGIN", new_y="NEXT",
    )
    pdf.cell(0, 7, _sanitize_text(f"Generated: {timestamp}"), align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(20)

    top_services = sub_summary.get("top_services", [])
    if top_services:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(0, 8, "Top Deployed Services:", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for svc in top_services[:8]:
            pdf.cell(0, 6, _sanitize_text(f"  {svc}"), align="C", new_x="LMARGIN", new_y="NEXT")

    # Executive Summary
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(0, 102, 204)
    pdf.cell(0, 12, "Executive Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(40, 40, 40)

    total_feed = dig_summary.get("total_feed_updates", 0)
    relevant = dig_summary.get("relevant_updates", 0)
    action_req = dig_summary.get("action_required", 0)
    num_sections = dig_summary.get("sections", 0)

    metrics = [
        ("Total Azure Updates in Feed", str(total_feed)),
        ("Updates Relevant to Your Environment", str(relevant)),
        ("Action Required (Urgent)", str(action_req)),
        ("Categories Identified", str(num_sections)),
    ]

    for label, value in metrics:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(120, 8, f"  {label}:")
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 8, value, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)

    # Section overview
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 10, "Sections Overview", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    for section in sections:
        color = _get_section_color(section.get("priority", 99))
        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 10)
        section_name = section.get("section", "Unknown")
        total_count = section.get("total_count", 0)
        service_groups = section.get("service_groups", [])
        num_services = len(service_groups)
        pdf.cell(
            0, 8,
            _sanitize_text(f"  {section_name} ({total_count} updates across {num_services} services)"),
            fill=True, new_x="LMARGIN", new_y="NEXT",
        )

        pdf.set_text_color(60, 60, 60)
        pdf.set_font("Helvetica", "", 9)
        for sg in service_groups[:5]:
            svc_name = sg.get("service", "Unknown")
            upd_count = sg.get("update_count", 0)
            breakdown = sg.get("status_breakdown", {})
            breakdown_str = ", ".join(f"{k}: {v}" for k, v in breakdown.items())
            pdf.cell(
                0, 5,
                _sanitize_text(f"    - {svc_name}: {upd_count} updates ({breakdown_str})"),
                new_x="LMARGIN", new_y="NEXT",
            )
        if len(service_groups) > 5:
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(
                0, 5,
                _sanitize_text(f"    ... and {len(service_groups) - 5} more services"),
                new_x="LMARGIN", new_y="NEXT",
            )
        pdf.ln(2)

    # Digest Highlights
    if digest_highlights:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(220, 53, 69)
        pdf.cell(0, 12, "Top Priority Updates -- Don't Miss These", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        highlight_color = (220, 53, 69)
        for i, update in enumerate(digest_highlights[:10], 1):
            _render_update_item(pdf, update, i, highlight_color, "Top Priority Updates")

    if report_type == "executive":
        return pdf.output()

    # Per-Section Detail Pages
    for section in sections:
        color = _get_section_color(section.get("priority", 99))
        section_name = section.get("section", "Unknown")
        critical_highlights = section.get("critical_highlights", [])
        service_groups = section.get("service_groups", [])

        pdf.add_page()

        pdf.set_fill_color(*color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 14)
        total_count = section.get("total_count", 0)
        pdf.cell(
            0, 10,
            _sanitize_text(f"  {section_name} ({total_count} updates)"),
            fill=True, new_x="LMARGIN", new_y="NEXT",
        )
        pdf.ln(4)

        if critical_highlights:
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(0, 8, "Critical Highlights:", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

            for i, update in enumerate(critical_highlights, 1):
                _render_update_item(pdf, update, i, color, section_name)

        if service_groups:
            if pdf.get_y() > 220:
                pdf.add_page()
                pdf.set_fill_color(*color)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Helvetica", "B", 14)
                pdf.cell(0, 10, _sanitize_text(f"  {section_name} -- Service Groups"), fill=True, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(4)

            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(0, 8, "All Updates by Service:", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

            for sg in service_groups:
                if pdf.get_y() > 250:
                    pdf.add_page()
                    pdf.set_fill_color(*color)
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_font("Helvetica", "B", 14)
                    pdf.cell(0, 10, _sanitize_text(f"  {section_name} -- Service Groups (continued)"), fill=True, new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(4)

                svc_name = sg.get("service", "Unknown")
                upd_count = sg.get("update_count", 0)
                breakdown = sg.get("status_breakdown", {})
                affected_count = sg.get("total_affected_resources", 0)
                max_rel = sg.get("max_relevance", 0)

                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(40, 40, 40)
                breakdown_str = ", ".join(f"{k}: {v}" for k, v in breakdown.items())
                pdf.multi_cell(
                    0, 6,
                    _sanitize_text(f"{svc_name} -- {upd_count} updates ({breakdown_str})"),
                    new_x="LMARGIN", new_y="NEXT",
                )

                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(100, 100, 100)
                meta = f"Affected resources: {affected_count}   Max relevance: {max_rel:.1%}"
                pdf.cell(0, 4, _sanitize_text(f"   {meta}"), new_x="LMARGIN", new_y="NEXT")

                top_updates = sg.get("top_updates", [])
                if top_updates:
                    top = top_updates[0]
                    pdf.set_font("Helvetica", "I", 9)
                    pdf.set_text_color(60, 60, 60)
                    pdf.multi_cell(
                        0, 5,
                        _sanitize_text(f"   Top: {_truncate(top.get('title', ''), 120)}"),
                        new_x="LMARGIN", new_y="NEXT",
                    )
                    link = top.get("link", "")
                    if link:
                        pdf.set_font("Helvetica", "", 7)
                        pdf.set_text_color(0, 102, 204)
                        pdf.cell(0, 4, f"   {_truncate(link, 90)}", link=link, new_x="LMARGIN", new_y="NEXT")

                pdf.ln(3)

    return pdf.output()


# ── Public API ───────────────────────────────────────────────────────


async def generate_report(
    subscription_id: str | None = None,
    report_type: str = "full",
    highlights_per_section: int = 3,
    output_path: str | None = None,
) -> str:
    """Generate a PDF report of personalised Azure Updates."""
    try:
        digest_json = await get_personalized_updates(
            subscription_id=subscription_id,
            highlights_per_section=highlights_per_section,
        )
        digest = json.loads(digest_json)

        if digest.get("status") != "success":
            return error_response(
                "Failed to generate updates digest: "
                + digest.get("error", {}).get("message", "Unknown error")
            )

        digest_data = digest["data"]
        pdf_bytes = _build_pdf(digest_data, report_type=report_type)

        if output_path:
            output_path = validate_output_path(output_path, [".pdf"])
        else:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(
                tempfile.gettempdir(),
                f"azure_updates_report_{timestamp}.pdf",
            )

        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        sub_summary = digest_data.get("subscription_summary", {})
        dig_summary = digest_data.get("digest_summary", {})

        return success_response(
            {
                "report_path": output_path,
                "report_type": report_type,
                "file_size_bytes": len(pdf_bytes),
                "subscription_id": sub_summary.get("subscription_id", ""),
                "total_resources": sub_summary.get("total_resources", 0),
                "relevant_updates": dig_summary.get("relevant_updates", 0),
                "sections": dig_summary.get("sections", 0),
                "action_required": dig_summary.get("action_required", 0),
            },
            scope=f"subscriptions/{sub_summary.get('subscription_id', '')}",
            extra_meta={
                "reportType": report_type,
                "highlightsPerSection": highlights_per_section,
            },
        )
    except ImportError:
        logger.exception("fpdf2 not installed")
        return error_response(
            "fpdf2 is required for PDF generation. Install it with: pip install fpdf2>=2.7.0",
            code="MissingDependency",
        )
    except Exception as e:
        logger.exception("generate_report failed")
        return error_response(sanitize_error_message(str(e)))
