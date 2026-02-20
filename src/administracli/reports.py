"""
Report generation: balance sheet and profit-and-loss statement.
"""

from decimal import Decimal

from rich.table import Table

from administracli.models import Administracli, Categories

# Mapping of categories to report sections
BALANCE_SHEET_CATEGORIES = {
    Categories.CAPITAL,
    Categories.CROSS_BOOKING,
}

PROFIT_AND_LOSS_CATEGORIES = {
    Categories.GENERAL_COSTS,
    Categories.FINANCIAL_COSTS,
    Categories.FINANCIAL_REVENUE,
    Categories.INCOMING_INVOICE,
    Categories.OUTGOING_INVOICE,
    Categories.VAT,
}


def _sum_by_category(data: Administracli) -> dict[str, Decimal]:
    """Sum transaction amounts grouped by _category."""
    totals: dict[str, Decimal] = {}
    for t in data.transactions:
        cat = t._category
        if cat is None:
            continue
        totals[cat] = totals.get(cat, Decimal(0)) + t.amount
    return totals


def balance_sheet(data: Administracli) -> Table:
    """Generate a Rich table for the balance sheet."""
    totals = _sum_by_category(data)
    table = Table(title="Balance Sheet")
    table.add_column("Category", style="cyan")
    table.add_column("Amount", style="green", justify="right")

    grand_total = Decimal(0)
    for cat in sorted(BALANCE_SHEET_CATEGORIES, key=lambda c: c.value):
        amount = totals.get(str(cat), Decimal(0))
        grand_total += amount
        table.add_row(str(cat), f"{amount:.2f}")

    table.add_section()
    table.add_row("Total", f"{grand_total:.2f}", style="bold")
    return table


def profit_and_loss(data: Administracli) -> Table:
    """Generate a Rich table for the profit-and-loss statement."""
    totals = _sum_by_category(data)
    table = Table(title="Profit and Loss")
    table.add_column("Category", style="cyan")
    table.add_column("Amount", style="green", justify="right")

    grand_total = Decimal(0)
    for cat in sorted(PROFIT_AND_LOSS_CATEGORIES, key=lambda c: c.value):
        amount = totals.get(str(cat), Decimal(0))
        grand_total += amount
        table.add_row(str(cat), f"{amount:.2f}")

    table.add_section()
    table.add_row("Total", f"{grand_total:.2f}", style="bold")
    return table



