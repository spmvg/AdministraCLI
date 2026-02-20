"""
Report generation: balance sheet and profit-and-loss statement.
"""

from decimal import Decimal

from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from administracli.models import Administracli, Categories

# Balance sheet classification
ASSET_CATEGORIES = [
    Categories.CROSS_BOOKING,
]

EQUITY_LIABILITY_CATEGORIES = [
    Categories.CAPITAL,
]

# P&L classification (order matters for presentation)
REVENUE_CATEGORIES = [
    Categories.OUTGOING_INVOICE,
    Categories.FINANCIAL_REVENUE,
]

COST_CATEGORIES = [
    Categories.INCOMING_INVOICE,
    Categories.GENERAL_COSTS,
    Categories.FINANCIAL_COSTS,
    Categories.VAT,
]


def _sum_by_category(data: Administracli) -> dict[str, Decimal]:
    """Sum transaction amounts grouped by _category."""
    totals: dict[str, Decimal] = {}
    for t in data.transactions:
        cat = t._category
        if cat is None:
            continue
        totals[cat] = totals.get(cat, Decimal(0)) + t.amount
    return totals


def _amount_str(amount: Decimal) -> str:
    """Format a decimal amount for display."""
    return f"{amount:,.2f}"


def balance_sheet(data: Administracli) -> Panel:
    """Generate a balance sheet with assets on the left, equity/liabilities on the right."""
    totals = _sum_by_category(data)

    # --- Assets side ---
    assets_table = Table(
        show_header=True,
        show_edge=False,
        pad_edge=False,
        expand=True,
    )
    assets_table.add_column("Assets", style="cyan", ratio=3)
    assets_table.add_column("", justify="right", ratio=2)

    assets_total = Decimal(0)
    for cat in ASSET_CATEGORIES:
        amount = totals.get(str(cat), Decimal(0))
        assets_total += amount
        assets_table.add_row(str(cat), _amount_str(amount))

    assets_table.add_section()
    assets_table.add_row(
        Text("Total assets", style="bold"),
        Text(_amount_str(assets_total), style="bold"),
    )

    # --- Equity & liabilities side ---
    eq_table = Table(
        show_header=True,
        show_edge=False,
        pad_edge=False,
        expand=True,
    )
    eq_table.add_column("Equity & Liabilities", style="cyan", ratio=3)
    eq_table.add_column("", justify="right", ratio=2)

    # Retained earnings come from P&L result
    pl_result = _net_result(totals)

    eq_total = Decimal(0)
    for cat in EQUITY_LIABILITY_CATEGORIES:
        amount = totals.get(str(cat), Decimal(0))
        eq_total += amount
        eq_table.add_row(str(cat), _amount_str(amount))

    eq_table.add_row("Retained earnings", _amount_str(pl_result))
    eq_total += pl_result

    eq_table.add_section()
    eq_table.add_row(
        Text("Total equity & liabilities", style="bold"),
        Text(_amount_str(eq_total), style="bold"),
    )

    return Panel(
        Columns([assets_table, eq_table], expand=True, equal=True),
        title="[bold]Balance Sheet[/bold]",
        border_style="green",
        expand=True,
    )


def _net_result(totals: dict[str, Decimal]) -> Decimal:
    """Compute net result (revenue - costs)."""
    revenue = sum(totals.get(str(c), Decimal(0)) for c in REVENUE_CATEGORIES)
    costs = sum(totals.get(str(c), Decimal(0)) for c in COST_CATEGORIES)
    return revenue - costs


def profit_and_loss(data: Administracli) -> Panel:
    """Generate a profit-and-loss statement: revenue first, then costs, then net result."""
    totals = _sum_by_category(data)

    table = Table(
        show_header=True,
        show_edge=False,
        pad_edge=False,
        expand=True,
    )
    table.add_column("", style="cyan", ratio=3)
    table.add_column("", justify="right", ratio=1)
    table.add_column("", justify="right", ratio=1)

    # --- Revenue ---
    table.add_row(Text("Revenue", style="bold underline"), "", "")
    revenue_total = Decimal(0)
    for cat in REVENUE_CATEGORIES:
        amount = totals.get(str(cat), Decimal(0))
        revenue_total += amount
        table.add_row(f"  {cat}", _amount_str(amount), "")

    table.add_row(
        Text("Total revenue", style="bold"),
        "",
        Text(_amount_str(revenue_total), style="bold"),
    )
    table.add_row("", "", "")

    # --- Costs ---
    table.add_row(Text("Costs", style="bold underline"), "", "")
    costs_total = Decimal(0)
    for cat in COST_CATEGORIES:
        amount = totals.get(str(cat), Decimal(0))
        costs_total += amount
        table.add_row(f"  {cat}", _amount_str(amount), "")

    table.add_row(
        Text("Total costs", style="bold"),
        "",
        Text(_amount_str(costs_total), style="bold"),
    )

    # --- Net result ---
    table.add_section()
    net = revenue_total - costs_total
    style = "bold green" if net >= 0 else "bold red"
    table.add_row(
        Text("Net result", style=style),
        "",
        Text(_amount_str(net), style=style),
    )

    return Panel(
        table,
        title="[bold]Profit and Loss[/bold]",
        border_style="green",
        expand=True,
    )
