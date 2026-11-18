"""
planner.render.terminal
Formats trace, plan summary tables, validation badges, and red rejection boxes using rich.
Always prints the full trace first even if errors occurred.
Plain text remains readable when copied.
"""

import sys
from typing import Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()

def render_terminal(result: Optional[Any], trace: Any) -> None:
    """Print formatted output to console."""
    # 1. Always print the exact trace first
    trace_text = trace.format_text()
    console.print(trace_text)
    console.print()

    if not result or not result.plan:
        return

    plan = result.plan
    people = plan.get("people", {})
    venue = plan.get("venue", {})
    food = plan.get("food", {})
    judging = plan.get("judging", {})
    budget = plan.get("budget", {})
    schedule = plan.get("schedule", {})

    # 2. Rejection alerts (pinned prominently in red)
    reject_events = [e for e in trace.events if e.get("type") == "REJECT"]
    for rej in reject_events:
        rej_msg = rej.get("text", "")
        panel = Panel(
            Text(rej_msg, style="bold red"),
            title="[bold red]MESSAGE REJECTED (Plan Kept Unchanged)[/bold red]",
            border_style="red"
        )
        console.print(panel)

    # 3. Validation Badges Table
    check_table = Table(title="Validation Checks (6/6 Graded Checks)", show_header=True, header_style="bold cyan")
    check_table.add_column("Check", style="bold")
    check_table.add_column("Status")
    check_table.add_column("Details")

    for c in getattr(result, "checks", []):
        ok = c.get("ok", False)
        status_str = "[bold green]PASS[/bold green]" if ok else "[bold red]FAIL[/bold red]"
        check_table.add_row(c.get("name", ""), status_str, c.get("detail", ""))

    console.print(check_table)
    console.print()

    # 4. Plan Overview Table
    plan_table = Table(title="Hackathon Event Plan Overview", show_header=True, header_style="bold magenta")
    plan_table.add_column("Area", style="bold")
    plan_table.add_column("Key Figures / Selections")
    plan_table.add_column("Cost (Rs)", justify="right")

    # People / Venue
    venue_info = f"{venue.get('name')} (Cap: {venue.get('capacity')}, Headcount: {people.get('total')})"
    plan_table.add_row("Venue", venue_info, f"{venue.get('cost', 0):,}")

    # Food
    food_info = f"{food.get('count')} boxes @ Rs {food.get('unit_price')} ({food.get('tier')} tier)"
    plan_table.add_row("Food", food_info, f"{food.get('cost', 0):,}")

    # Judging
    judg_info = f"{judging.get('needed')} judges ({judging.get('confirmed')} confirmed, {judging.get('reserves')} reserves)"
    plan_table.add_row("Judging", judg_info, f"{judging.get('cost', 0):,}")

    # Committed Spent
    committed_sum = sum(line.get("amount", 0) for line in budget.get("lines", []) if line.get("category") == "committed")
    plan_table.add_row("Committed Spend", "Prizes, Internet, Printing, etc.", f"{committed_sum:,}")

    # Total & Remaining
    plan_table.add_section()
    plan_table.add_row(
        "[bold]Total Spend[/bold]",
        f"Budget Cap: Rs {budget.get('budget_total', 0):,}",
        f"[bold]{budget.get('total', 0):,}[/bold]"
    )
    rem = budget.get("remaining", 0)
    rem_style = "bold green" if rem >= 0 else "bold red"
    plan_table.add_row(
        f"[{rem_style}]Remaining Balance[/{rem_style}]",
        "Available surplus",
        f"[{rem_style}]{rem:,}[/{rem_style}]"
    )

    console.print(plan_table)
    console.print()
