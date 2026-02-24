"""Interactive console client for Azure Cost Management MCP Server.

Connects to the MCP server via stdio transport, provides a menu-driven
interface to all 15 cost management tools, and renders results as
rich terminal tables.

Usage:
    azure-cost-console                      # interactive mode
    azure-cost-console --tool costs         # quick-command mode
    azure-cost-console --subscription-id X  # override subscription
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

console = Console(stderr=True)

# ── Tool Categories ──────────────────────────────────────────────────

TOOL_CATEGORIES = [
    {
        "key": "1",
        "name": "Cost Queries",
        "icon": "$",
        "tools": [
            ("query_subscription_costs_tool", "Query Subscription Costs",
             "Query costs across an entire subscription"),
            ("query_resource_group_costs_tool", "Query Resource Group Costs",
             "Query costs for a specific resource group"),
            ("query_management_group_costs_tool", "Query Management Group Costs",
             "Query costs across a management group"),
            ("compare_costs_tool", "Compare Costs Between Periods",
             "Compare spend across two time periods"),
        ],
    },
    {
        "key": "2",
        "name": "Forecasts",
        "icon": "^",
        "tools": [
            ("get_cost_forecast_tool", "Get Cost Forecast",
             "Forecast future costs for a subscription or resource group"),
        ],
    },
    {
        "key": "3",
        "name": "Budgets",
        "icon": "#",
        "tools": [
            ("list_budgets_tool", "List Budgets", "List all cost budgets"),
            ("get_budget_tool", "Get Budget Details",
             "Get details of a specific budget"),
            ("create_budget_tool", "Create Budget",
             "Create a new cost budget with thresholds"),
            ("update_budget_tool", "Update Budget",
             "Modify an existing budget"),
            ("delete_budget_tool", "Delete Budget", "Remove a budget"),
        ],
    },
    {
        "key": "4",
        "name": "Alerts",
        "icon": "!",
        "tools": [
            ("list_cost_alerts_tool", "List Cost Alerts",
             "List all cost alerts"),
            ("dismiss_alert_tool", "Dismiss Alert",
             "Dismiss a specific cost alert"),
        ],
    },
    {
        "key": "5",
        "name": "Recommendations",
        "icon": "*",
        "tools": [
            ("list_cost_recommendations_tool", "List Cost Recommendations",
             "Azure Advisor cost optimization suggestions"),
            ("get_recommendation_details_tool", "Get Recommendation Details",
             "Detailed info about a specific recommendation"),
        ],
    },
    {
        "key": "6",
        "name": "Anomaly Detection",
        "icon": "~",
        "tools": [
            ("list_anomalies_tool", "Detect Cost Anomalies",
             "Find unusual spending spikes"),
        ],
    },
]

QUICK_COMMANDS: dict[str, str] = {
    "costs": "query_subscription_costs_tool",
    "rg": "query_resource_group_costs_tool",
    "mg": "query_management_group_costs_tool",
    "compare": "compare_costs_tool",
    "forecast": "get_cost_forecast_tool",
    "budgets": "list_budgets_tool",
    "alerts": "list_cost_alerts_tool",
    "recommendations": "list_cost_recommendations_tool",
    "recs": "list_cost_recommendations_tool",
    "anomalies": "list_anomalies_tool",
}

# ── Console Application ─────────────────────────────────────────────


class CostManagementConsole:
    """Interactive console client for the Azure Cost Management MCP Server."""

    def __init__(self, session: ClientSession, subscription_id: str = ""):
        self.session = session
        self.tools: dict[str, Any] = {}
        self.subscription_id = subscription_id or os.environ.get(
            "AZURE_SUBSCRIPTION_ID", ""
        )
        self.last_result: str | None = None

    # ── Lifecycle ────────────────────────────────────────────────────

    async def initialize(self) -> int:
        """Load available tools from the server."""
        result = await self.session.list_tools()
        for tool in result.tools:
            self.tools[tool.name] = tool
        return len(self.tools)

    async def run(self) -> None:
        """Main interactive loop."""
        tool_count = await self.initialize()
        self._show_banner(tool_count)

        while True:
            try:
                choice = self._main_menu()
                if choice is None or choice.lower() in ("q", "quit", "exit"):
                    console.print("\n[dim]Goodbye![/dim]\n")
                    break
                if choice.lower() in ("h", "help"):
                    self._show_help()
                    continue
                if choice.lower() == "r":
                    if self.last_result:
                        self._show_raw_json(self.last_result)
                    else:
                        console.print("[dim]No previous result.[/dim]")
                    continue
                if choice.lower() == "e":
                    self._export_result()
                    continue
                # Quick command
                if choice.lower() in QUICK_COMMANDS:
                    await self._run_tool(QUICK_COMMANDS[choice.lower()])
                    continue
                # Direct tool name
                if choice in self.tools:
                    await self._run_tool(choice)
                    continue
                # Category selection (1-6)
                category = self._find_category(choice)
                if category:
                    tool_name = self._tool_menu(category)
                    if tool_name:
                        await self._run_tool(tool_name)
                    continue

                console.print(
                    f"[red]Unknown command:[/red] {choice}. "
                    "Type [bold]h[/bold] for help."
                )
            except KeyboardInterrupt:
                console.print("\n[dim]Use 'q' to quit.[/dim]")
            except EOFError:
                break

    async def run_single(self, tool_name: str, args_json: str = "") -> None:
        """Execute a single tool and exit (non-interactive mode)."""
        await self.initialize()

        # Resolve quick command
        resolved = QUICK_COMMANDS.get(tool_name, tool_name)
        if resolved not in self.tools:
            console.print(f"[red]Unknown tool: {tool_name}[/red]")
            console.print(
                "[dim]Available: "
                + ", ".join(sorted(self.tools.keys()))
                + "[/dim]"
            )
            return

        if args_json:
            args = json.loads(args_json)
        else:
            tool = self.tools[resolved]
            args = self._prompt_parameters(tool)
            if args is None:
                return

        # Auto-fill subscription_id
        if "subscription_id" in self.tools[resolved].inputSchema.get(
            "properties", {}
        ):
            args.setdefault("subscription_id", self.subscription_id)

        console.print()
        with console.status(
            "[bold cyan]Querying Azure...[/bold cyan]", spinner="dots"
        ):
            try:
                result = await self.session.call_tool(resolved, arguments=args)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                return

        result_text = "".join(
            c.text for c in result.content if hasattr(c, "text")
        )
        self.last_result = result_text
        self._display_result(result_text, resolved)

    # ── Menus ────────────────────────────────────────────────────────

    def _show_banner(self, tool_count: int) -> None:
        sub_display = (
            self.subscription_id[:13] + "..."
            if self.subscription_id
            else "[yellow]not set[/yellow]"
        )
        lines = [
            "[bold cyan]Azure Cost Management Console[/bold cyan]",
            "",
            f"[green]Connected[/green]  [dim]|[/dim]  "
            f"[dim]{tool_count} tools[/dim]  [dim]|[/dim]  "
            f"[dim]Sub:[/dim] {sub_display}",
        ]
        console.print()
        console.print(Panel("\n".join(lines), border_style="cyan", padding=(1, 2)))

    def _main_menu(self) -> str | None:
        console.print()
        grid = Table(
            show_header=False, show_edge=False, box=None, padding=(0, 4)
        )
        grid.add_column(min_width=30)
        grid.add_column(min_width=30)

        cats = TOOL_CATEGORIES
        for i in range(0, len(cats), 2):
            left = (
                f"[bold cyan][{cats[i]['key']}][/bold cyan] "
                f"{cats[i]['icon']}  {cats[i]['name']}"
            )
            right = ""
            if i + 1 < len(cats):
                right = (
                    f"[bold cyan][{cats[i + 1]['key']}][/bold cyan] "
                    f"{cats[i + 1]['icon']}  {cats[i + 1]['name']}"
                )
            grid.add_row(left, right)

        console.print(grid)
        console.print()
        console.print(
            "[dim]  [h] Help   [r] Raw JSON   [e] Export   [q] Quit[/dim]"
        )
        console.print()

        try:
            return console.input("[bold green]> [/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            return "q"

    def _find_category(self, choice: str) -> dict | None:
        for cat in TOOL_CATEGORIES:
            if cat["key"] == choice:
                return cat
        return None

    def _tool_menu(self, category: dict) -> str | None:
        console.print()
        console.print(
            f"[bold]{category['icon']}  {category['name']}[/bold]"
        )
        console.print("[dim]" + "-" * 50 + "[/dim]")

        tools = category["tools"]
        for i, (_, label, desc) in enumerate(tools, 1):
            console.print(f"  [bold cyan][{i}][/bold cyan] {label}")
            console.print(f"      [dim]{desc}[/dim]")

        console.print(f"\n  [dim][b] Back[/dim]")
        console.print()

        try:
            choice = console.input("[bold green]> [/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            return None

        if choice.lower() in ("b", "back", ""):
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(tools):
                return tools[idx][0]  # tool name
        except ValueError:
            pass
        console.print("[red]Invalid selection.[/red]")
        return None

    # ── Parameter Prompting ──────────────────────────────────────────

    def _prompt_parameters(self, tool: Any) -> dict | None:
        """Prompt user for each tool parameter with smart defaults."""
        args: dict[str, Any] = {}
        schema = tool.inputSchema
        properties: dict = schema.get("properties", {})
        required: set = set(schema.get("required", []))

        console.print()
        console.print(
            "[dim]Fill in parameters (Enter = default, empty = skip optional):[/dim]"
        )
        console.print()

        for param_name, param_info in properties.items():
            param_type = param_info.get("type", "string")
            description = param_info.get("description", "")
            default = param_info.get("default")
            is_required = param_name in required

            # Auto-fill subscription_id from env
            if param_name == "subscription_id" and self.subscription_id:
                args[param_name] = self.subscription_id
                short = self.subscription_id[:13] + "..."
                console.print(
                    f"  [cyan]{param_name}[/cyan]: {short} [dim](auto)[/dim]"
                )
                continue

            # Build the prompt line
            req_mark = " [red]*[/red]" if is_required else ""
            default_hint = ""
            if default is not None and default != "":
                default_hint = f" [dim]\\[{default}][/dim]"

            if description:
                console.print(f"  [dim]{description}[/dim]")

            try:
                value = console.input(
                    f"  [cyan]{param_name}[/cyan]{req_mark}{default_hint}: "
                ).strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Cancelled.[/dim]")
                return None

            # Apply default if user pressed Enter
            if value == "":
                if default is not None:
                    value = default
                elif is_required:
                    console.print(
                        f"  [red]{param_name} is required.[/red]"
                    )
                    return None
                else:
                    continue  # skip optional empty param

            # Type coercion
            if param_type == "integer":
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    console.print(
                        f"  [red]Expected integer for {param_name}.[/red]"
                    )
                    return None
            elif param_type == "number":
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    console.print(
                        f"  [red]Expected number for {param_name}.[/red]"
                    )
                    return None
            elif param_type == "boolean":
                if isinstance(value, str):
                    value = value.lower() in ("true", "1", "yes", "y")

            args[param_name] = value

        return args

    # ── Tool Execution ───────────────────────────────────────────────

    async def _run_tool(self, tool_name: str) -> None:
        tool = self.tools.get(tool_name)
        if not tool:
            console.print(f"[red]Tool not found: {tool_name}[/red]")
            return

        label = tool_name.replace("_tool", "").replace("_", " ").title()
        console.print(f"\n[bold]{label}[/bold]")
        console.print("[dim]" + "-" * 50 + "[/dim]")

        args = self._prompt_parameters(tool)
        if args is None:
            return

        console.print()
        with console.status(
            "[bold cyan]Querying Azure...[/bold cyan]", spinner="dots"
        ):
            try:
                result = await self.session.call_tool(
                    tool_name, arguments=args
                )
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                return

        result_text = "".join(
            c.text for c in result.content if hasattr(c, "text")
        )
        self.last_result = result_text
        self._display_result(result_text, tool_name)

    # ── Result Display ───────────────────────────────────────────────

    def _display_result(self, result_text: str, tool_name: str) -> None:
        try:
            data = json.loads(result_text)
        except json.JSONDecodeError:
            console.print(result_text)
            return

        status = data.get("status", "unknown")
        if status == "error":
            err = data.get("error", {})
            console.print(
                Panel(
                    f"[red]{err.get('message', 'Unknown error')}[/red]",
                    title="Error",
                    border_style="red",
                )
            )
            return

        # Metadata strip
        meta = data.get("metadata", {})
        if meta:
            parts = [
                f"[dim]{k}:[/dim] {v}"
                for k, v in meta.items()
                if k not in ("generated_at",) and v
            ]
            if parts:
                console.print(f"\n  {'  |  '.join(parts)}")

        raw_data = data.get("data", data)

        # Normalise: if data is a list of rows, wrap it in a dict
        if isinstance(raw_data, list):
            result_data = {"rows": raw_data}
        else:
            result_data = raw_data

        displayed = (
            self._try_recommendation_table(result_data, tool_name)
            or self._try_anomaly_table(result_data, tool_name)
            or self._try_comparison_table(result_data, tool_name)
            or self._try_forecast_table(result_data, tool_name)
            or self._try_budget_table(result_data, tool_name)
            or self._try_alert_table(result_data, tool_name)
            or self._try_cost_table(result_data, tool_name)
        )

        if not displayed:
            self._show_raw_json(result_text)

        # Total line — compute from rows if no explicit total
        total = result_data.get("total_cost")
        if total is None and isinstance(raw_data, list) and raw_data:
            # Sum cost values from rows
            try:
                total = sum(
                    r.get("Cost", r.get("cost", r.get("amount", 0)))
                    for r in raw_data
                    if isinstance(r, dict)
                )
            except (TypeError, ValueError):
                total = None

        if total is not None:
            currency = result_data.get(
                "currency", meta.get("currency", "USD")
            )
            console.print(
                f"\n  [bold]Total: {currency} {total:,.2f}[/bold]"
            )

        console.print(
            "\n  [dim]Tip: [b]r[/b] = raw JSON  |  [b]e[/b] = export to file[/dim]"
        )

    # ── Table renderers ──────────────────────────────────────────────

    def _try_cost_table(self, data: dict, tool_name: str) -> bool:
        """Render cost-query rows as a table."""
        if "query" not in tool_name and "cost" not in tool_name:
            return False
        rows = data.get("rows", [])
        if not rows or not isinstance(rows[0], dict):
            return False

        table = Table(
            title="Cost Breakdown", box=box.ROUNDED, padding=(0, 1)
        )
        first = rows[0]

        # Identify cost columns for right-justify and green styling
        cost_keys = {"Cost", "CostUSD", "cost", "amount", "totalCost", "totalCostUSD"}
        currency_keys = {"Currency", "currency", "BillingCurrency"}

        col_order = list(first.keys())
        for key in col_order:
            if key in cost_keys:
                table.add_column(key, style="green", justify="right")
            elif key in currency_keys:
                table.add_column(key, style="dim")
            else:
                table.add_column(key, style="cyan")

        # Sort by cost descending
        try:
            sorted_rows = sorted(
                rows,
                key=lambda r: r.get("Cost", r.get("cost", r.get("CostUSD", r.get("amount", 0)))),
                reverse=True,
            )
        except (TypeError, KeyError):
            sorted_rows = rows

        for row in sorted_rows[:50]:
            vals = []
            for key in col_order:
                v = row.get(key, "")
                vals.append(f"{v:,.2f}" if isinstance(v, float) else str(v))
            table.add_row(*vals)

        if len(rows) > 50:
            table.add_row(*[f"... ({len(rows) - 50} more)" if i == 0 else "" for i in range(len(col_order))])

        console.print()
        console.print(table)
        console.print(f"\n  [dim]{len(rows)} row(s)[/dim]")
        return True

    def _try_comparison_table(self, data: dict, tool_name: str) -> bool:
        if "compare" not in tool_name:
            return False
        comparison = data.get("comparison", [])
        if not comparison:
            return False

        table = Table(title="Cost Comparison", box=box.ROUNDED)
        table.add_column("Dimension", style="cyan")
        table.add_column("Period 1", justify="right", style="dim")
        table.add_column("Period 2", justify="right", style="green")
        table.add_column("Change", justify="right")
        table.add_column("Change %", justify="right")

        for row in comparison:
            change = row.get("change", 0)
            pct = row.get("change_percent", 0)
            if isinstance(change, (int, float)):
                sign = "+" if change > 0 else ""
                color = "red" if change > 0 else "green"
                ch_disp = f"[{color}]{sign}{change:,.2f}[/{color}]"
                pct_disp = f"[{color}]{sign}{pct:.1f}%[/{color}]"
            else:
                ch_disp, pct_disp = str(change), str(pct)

            table.add_row(
                row.get("dimension", row.get("group", "")),
                f"${row.get('period1_cost', 0):,.2f}",
                f"${row.get('period2_cost', 0):,.2f}",
                ch_disp,
                pct_disp,
            )

        console.print()
        console.print(table)
        return True

    def _try_forecast_table(self, data: dict, tool_name: str) -> bool:
        if "forecast" not in tool_name:
            return False
        forecast_rows = data.get("forecast", data.get("rows", []))
        if not forecast_rows:
            console.print("\n  [dim]No forecast data returned.[/dim]")
            return True

        table = Table(title="Cost Forecast", box=box.ROUNDED)
        table.add_column("Date", style="cyan")
        table.add_column("Type", style="dim")
        table.add_column("Cost", justify="right", style="green")
        table.add_column("Low", justify="right", style="dim")
        table.add_column("High", justify="right", style="dim")

        for row in forecast_rows[:60]:
            if not isinstance(row, dict):
                continue
            cost = row.get("cost", row.get("amount", 0))
            low = row.get("low_bound", row.get("confidence_low"))
            high = row.get("high_bound", row.get("confidence_high"))
            table.add_row(
                str(row.get("date", row.get("usage_date", "")))[:10],
                row.get("cost_type", row.get("type", "")),
                f"${cost:,.2f}" if isinstance(cost, (int, float)) else str(cost),
                f"${low:,.2f}" if isinstance(low, (int, float)) else "",
                f"${high:,.2f}" if isinstance(high, (int, float)) else "",
            )

        console.print()
        console.print(table)

        total = data.get("total_forecast")
        if total is not None:
            console.print(
                f"\n  [bold]Forecasted Total: ${total:,.2f}[/bold]"
            )
        return True

    def _try_budget_table(self, data: dict, tool_name: str) -> bool:
        if "budget" not in tool_name:
            return False

        # Handle delete/create messages
        if "message" in data and "budgets" not in data:
            console.print(f"\n  [green]{data['message']}[/green]")
            return True

        budgets = data.get("budgets", data.get("rows", []))
        if isinstance(data, dict) and "budget_name" in data:
            budgets = [data]
        if not budgets:
            console.print("\n  [dim]No budgets found.[/dim]")
            return True

        table = Table(title="Budgets", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Amount", justify="right", style="green")
        table.add_column("Spent", justify="right", style="yellow")
        table.add_column("Utilization", justify="right")
        table.add_column("Time Grain", style="dim")

        for b in budgets:
            name = b.get("budget_name", b.get("name", ""))
            amount = b.get("amount", 0)
            spent = b.get("current_spend", {})
            if isinstance(spent, dict):
                spent_val = spent.get("amount", 0)
            else:
                spent_val = spent
            util = b.get("utilization_percent", 0)
            tg = b.get("time_grain", "")

            if isinstance(util, (int, float)):
                us = "green" if util < 80 else ("yellow" if util < 100 else "red bold")
                util_s = f"[{us}]{util:.1f}%[/{us}]"
            else:
                util_s = str(util)

            table.add_row(
                name,
                f"{amount:,.2f}" if isinstance(amount, (int, float)) else str(amount),
                f"{spent_val:,.2f}" if isinstance(spent_val, (int, float)) else str(spent_val),
                util_s,
                tg,
            )

        console.print()
        console.print(table)
        return True

    def _try_alert_table(self, data: dict, tool_name: str) -> bool:
        if "alert" not in tool_name:
            return False
        if "message" in data and "alerts" not in data:
            console.print(f"\n  [green]{data['message']}[/green]")
            return True

        alerts = data.get("alerts", data.get("rows", []))
        if not alerts:
            console.print("\n  [dim]No cost alerts.[/dim]")
            return True

        table = Table(title="Cost Alerts", box=box.ROUNDED)
        table.add_column("Status", style="bold")
        table.add_column("Type", style="cyan")
        table.add_column("Description")
        table.add_column("Amount", justify="right", style="green")
        table.add_column("Created", style="dim")

        for a in alerts:
            st = a.get("status", "")
            sc = "green" if st == "Resolved" else ("yellow" if st == "Active" else "red")
            table.add_row(
                f"[{sc}]{st}[/{sc}]",
                a.get("alert_type", a.get("type", "")),
                str(a.get("description", ""))[:60],
                str(a.get("amount", "")),
                str(a.get("created_date", a.get("creation_time", "")))[:10],
            )

        console.print()
        console.print(table)
        console.print(f"\n  [dim]{len(alerts)} alert(s)[/dim]")
        return True

    def _try_recommendation_table(self, data: dict, tool_name: str) -> bool:
        if "recommendation" not in tool_name:
            return False
        recs = data.get("recommendations", data.get("rows", []))
        if isinstance(data, dict) and "recommendation_id" in data:
            recs = [data]
        if not recs:
            console.print("\n  [dim]No cost recommendations.[/dim]")
            return True

        table = Table(
            title="Cost Optimization Recommendations", box=box.ROUNDED
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Impact", style="bold")
        table.add_column("Problem")
        table.add_column("Savings", justify="right", style="green")
        table.add_column("Resource", style="cyan")

        for i, r in enumerate(recs[:25], 1):
            impact = r.get("impact", "")
            ic = "red" if impact == "High" else ("yellow" if impact == "Medium" else "dim")
            savings = r.get("estimatedSavings", r.get("estimated_savings", r.get("savings_amount", "")))
            s_disp = f"${float(savings):,.2f}" if savings else "-"
            problem = r.get("shortDescription", r.get("short_description", r.get("problem", "")))
            resource = r.get("impactedValue", r.get("impacted_resource", r.get("resource_name", "")))
            table.add_row(
                str(i),
                f"[{ic}]{impact}[/{ic}]",
                str(problem or "")[:55],
                s_disp,
                str(resource or "")[:35],
            )

        console.print()
        console.print(table)
        console.print(f"\n  [dim]{len(recs)} recommendation(s)[/dim]")
        return True

    def _try_anomaly_table(self, data: dict, tool_name: str) -> bool:
        if "anomal" not in tool_name:
            return False
        anomalies = data.get("anomalies", data.get("rows", []))
        if not anomalies:
            console.print("\n  [green]No cost anomalies detected.[/green]")
            return True

        table = Table(title="Cost Anomalies", box=box.ROUNDED)
        table.add_column("Date", style="cyan")
        table.add_column("Actual", justify="right", style="red bold")
        table.add_column("Expected", justify="right", style="dim")
        table.add_column("Deviation", justify="right", style="yellow")
        table.add_column("Service", style="cyan")

        for a in anomalies:
            actual = a.get("actual_cost", 0)
            expected = a.get("expected_cost", a.get("rolling_average", 0))
            dev = a.get("deviation_percent", a.get("std_deviations", 0))
            table.add_row(
                str(a.get("date", ""))[:10],
                f"${actual:,.2f}" if isinstance(actual, (int, float)) else str(actual),
                f"${expected:,.2f}" if isinstance(expected, (int, float)) else str(expected),
                f"{dev:,.1f}%" if isinstance(dev, (int, float)) else str(dev),
                a.get("service", a.get("resource_group", "")),
            )

        console.print()
        console.print(table)
        console.print(
            f"\n  [bold red]{len(anomalies)} anomaly(ies) detected[/bold red]"
        )
        return True

    # ── Utilities ────────────────────────────────────────────────────

    def _show_raw_json(self, text: str) -> None:
        try:
            formatted = json.dumps(json.loads(text), indent=2)
        except json.JSONDecodeError:
            formatted = text
        console.print()
        console.print(
            Syntax(formatted, "json", theme="monokai", line_numbers=False)
        )

    def _export_result(self) -> None:
        if not self.last_result:
            console.print("[yellow]No result to export.[/yellow]")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cost_result_{ts}.json"
        export_dir = os.environ.get("AZURE_COST_MCP_EXPORT_DIR", ".")
        filepath = os.path.join(export_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                try:
                    json.dump(json.loads(self.last_result), f, indent=2)
                except json.JSONDecodeError:
                    f.write(self.last_result)
            console.print(
                f"\n  [green]Exported to:[/green] {os.path.abspath(filepath)}"
            )
        except Exception as e:
            console.print(f"\n  [red]Export failed: {e}[/red]")

    def _show_help(self) -> None:
        help_text = """\
[bold cyan]Azure Cost Management Console[/bold cyan]

[bold]Navigation:[/bold]
  [cyan]1-6[/cyan]     Select a tool category
  [cyan]q[/cyan]       Quit
  [cyan]h[/cyan]       Show this help
  [cyan]r[/cyan]       View last result as raw JSON
  [cyan]e[/cyan]       Export last result to a JSON file

[bold]Quick Commands[/bold] (type at the main prompt):
  [cyan]costs[/cyan]            Query subscription costs
  [cyan]rg[/cyan]               Query resource group costs
  [cyan]mg[/cyan]               Query management group costs
  [cyan]compare[/cyan]          Compare two time periods
  [cyan]forecast[/cyan]         Cost forecast
  [cyan]budgets[/cyan]          List budgets
  [cyan]alerts[/cyan]           List cost alerts
  [cyan]recommendations[/cyan]  List Advisor recommendations
  [cyan]anomalies[/cyan]        Detect spending anomalies

[bold]Parameters:[/bold]
  [red]*[/red] = required    Enter = accept default    empty = skip

[bold]Environment Variables:[/bold]
  AZURE_SUBSCRIPTION_ID       Default subscription
  AZURE_COST_MCP_EXPORT_DIR   Directory for exported files
  AZURE_COST_MCP_LOG_LEVEL    Server log level (DEBUG/INFO/WARNING)"""
        console.print(Panel(help_text, title="Help", border_style="cyan"))


# ── Entry & Connection ───────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Azure Cost Management - Interactive Console Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  azure-cost-console                            Interactive mode
  azure-cost-console --tool costs               Quick command
  azure-cost-console --tool list_budgets_tool   Specific tool
  azure-cost-console --subscription-id <guid>   Override subscription
        """,
    )
    parser.add_argument(
        "--subscription-id",
        default="",
        help="Azure subscription ID (overrides AZURE_SUBSCRIPTION_ID env var)",
    )
    parser.add_argument(
        "--tool",
        default="",
        help="Tool name or quick command to run (non-interactive)",
    )
    parser.add_argument(
        "--args",
        default="",
        help='Tool arguments as JSON string, e.g. \'{"timeframe":"MonthToDate"}\'',
    )
    parser.add_argument(
        "--server-command",
        default="",
        help="Custom command to start the MCP server (default: python -m azure_cost_mcp)",
    )
    return parser.parse_args()


async def _run_async(args: argparse.Namespace) -> None:
    """Establish MCP connection and launch console."""
    # Determine server command
    if args.server_command:
        parts = args.server_command.split()
        cmd, cmd_args = parts[0], parts[1:]
    else:
        cmd = sys.executable
        cmd_args = ["-m", "azure_cost_mcp"]

    # Forward env vars
    env = dict(os.environ)
    if args.subscription_id:
        env["AZURE_SUBSCRIPTION_ID"] = args.subscription_id

    server_params = StdioServerParameters(
        command=cmd,
        args=cmd_args,
        env=env,
    )

    console.print("\n[dim]Connecting to Azure Cost Management MCP Server...[/dim]")

    try:
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                app = CostManagementConsole(
                    session,
                    subscription_id=args.subscription_id,
                )

                if args.tool:
                    await app.run_single(args.tool, args.args)
                else:
                    await app.run()
    except FileNotFoundError:
        console.print("[red]Error: Could not start MCP server.[/red]")
        console.print(f"[dim]Tried: {cmd} {' '.join(cmd_args)}[/dim]")
        console.print(
            "[yellow]Make sure the package is installed: pip install -e .[/yellow]"
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Connection error: {e}[/red]")
        raise


def main() -> None:
    """Entry point for the console application."""
    args = parse_args()
    try:
        asyncio.run(_run_async(args))
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")


if __name__ == "__main__":
    main()
