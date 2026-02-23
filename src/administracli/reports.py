"""
Report generation: balance sheet and profit-and-loss statement.
"""

from decimal import Decimal

from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from administracli.closing import get_open_incoming_invoices, get_open_outgoing_invoices, get_total_vat_position
from administracli.models import Administracli, Categories

# Balance sheet classification
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
]


def _cit_advances(data: Administracli) -> Decimal:
    """Total CIT advance payments (bank outflow, so negative or zero)."""
    totals = _sum_by_category(data)
    return totals.get(str(Categories.CORPORATE_INCOME_TAX), Decimal(0))


def _sum_by_category(data: Administracli) -> dict[str, Decimal]:
    """Sum transaction amounts grouped by _category."""
    totals: dict[str, Decimal] = {}
    for t in data.transactions:
        cat = t._category
        if cat is None:
            continue
        totals[cat] = totals.get(cat, Decimal(0)) + t.amount
    return totals


def _sum_by_bank_account(data: Administracli) -> dict[str, Decimal]:
    """Sum transaction amounts grouped by bank account."""
    totals: dict[str, Decimal] = {}
    for t in data.transactions:
        totals[t.bank_account] = totals.get(t.bank_account, Decimal(0)) + t.amount
    return totals


def _amount_str(amount: Decimal) -> str:
    """Format a decimal amount for display."""
    return f"{amount:,.2f}"


def balance_sheet(data: Administracli) -> Panel:
    """Generate a balance sheet with assets on the left, equity/liabilities on the right."""
    totals = _sum_by_category(data)
    bank_totals = _sum_by_bank_account(data)
    open_incoming = get_open_incoming_invoices(data)  # creditors
    open_outgoing = get_open_outgoing_invoices(data)  # debtors
    vat_position = get_total_vat_position(data)  # positive = owe, negative = receivable

    # CIT position: advances are negative (money out), so -advances = amount prepaid
    advances = _cit_advances(data)  # negative or zero
    advances_paid = -advances  # positive = amount prepaid
    if data.cit_amount is not None:
        # Positive cit_amount = tax owed
        cit_receivable = advances_paid - data.cit_amount  # positive = overpaid (asset), negative = still owed (liability)
    else:
        # Not yet assessed: full advance is a prepayment (asset)
        cit_receivable = advances_paid  # positive = asset

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

    # Bank balances
    for account in sorted(bank_totals):
        amount = bank_totals[account]
        assets_total += amount
        assets_table.add_row(account, _amount_str(amount))

    # Debtors (open outgoing invoices: customers who still owe us)
    debtors_total = sum(oi.balance for oi in open_outgoing)
    if debtors_total != Decimal(0):
        assets_table.add_section()
        assets_table.add_row(Text("Debtors", style="bold"), "")
        for oi in open_outgoing:
            assets_table.add_row(f"  {oi.invoice.counterparty}", _amount_str(oi.balance))
        assets_total += debtors_total

    # VAT receivable (overpaid VAT)
    if vat_position < Decimal(0):
        assets_table.add_section()
        assets_table.add_row("VAT receivable", _amount_str(-vat_position))
        assets_total += -vat_position

    # CIT prepayment (asset: overpaid or not yet assessed)
    if cit_receivable > Decimal(0):
        assets_table.add_section()
        label = "CIT prepayment" if data.cit_amount is None else "CIT receivable"
        assets_table.add_row(label, _amount_str(cit_receivable))
        assets_total += cit_receivable

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

    eq_total = Decimal(0)
    for cat in EQUITY_LIABILITY_CATEGORIES:
        amount = totals.get(str(cat), Decimal(0))
        eq_total += amount
        eq_table.add_row(str(cat), _amount_str(amount))

    # Retained earnings come from P&L result
    pl_result = _net_result(data)
    eq_table.add_row("Retained earnings", _amount_str(pl_result))
    eq_total += pl_result

    # Creditors (open incoming invoices: suppliers we still owe)
    creditors_total = sum(oi.balance for oi in open_incoming)
    if creditors_total != Decimal(0):
        eq_table.add_section()
        eq_table.add_row(Text("Creditors", style="bold"), "")
        for oi in open_incoming:
            eq_table.add_row(f"  {oi.invoice.counterparty}", _amount_str(oi.balance))
        eq_total += creditors_total

    # VAT payable (still owe tax authority)
    if vat_position > Decimal(0):
        eq_table.add_section()
        eq_table.add_row("VAT payable", _amount_str(vat_position))
        eq_total += vat_position

    # CIT payable (liability: still owe more than paid)
    if cit_receivable < Decimal(0):
        eq_table.add_section()
        eq_table.add_row("CIT payable", _amount_str(-cit_receivable))
        eq_total += -cit_receivable

    eq_table.add_section()
    eq_table.add_row(
        Text("Total equity & liabilities", style="bold"),
        Text(_amount_str(eq_total), style="bold"),
    )

    return Panel(
        Columns([assets_table, eq_table], expand=True, equal=True),
        title="[bold]Balance Sheet (Differences)[/bold]",
        border_style="green",
        expand=True,
    )


def _result_before_tax(data: Administracli) -> Decimal:
    """Compute result before tax from P&L categories and open invoices."""
    totals = _sum_by_category(data)
    open_incoming = get_open_incoming_invoices(data)
    open_outgoing = get_open_outgoing_invoices(data)

    pl_categories = list(REVENUE_CATEGORIES) + list(COST_CATEGORIES)
    result = sum((totals.get(str(c), Decimal(0)) for c in pl_categories), Decimal(0))

    # Open outgoing invoices = revenue earned but not yet received
    result += sum(oi.balance for oi in open_outgoing)
    # Open incoming invoices = costs incurred but not yet paid (balance is positive = we owe)
    result -= sum(oi.balance for oi in open_incoming)

    return result


def _cit_expense(data: Administracli) -> Decimal:
    """CIT shown as expense in P&L.
    Only the definitive amount appears in P&L. If not yet assessed, nothing."""
    if data.cit_amount is not None:
        return data.cit_amount  # positive = tax owed
    return Decimal(0)


def _net_result(data: Administracli) -> Decimal:
    """Net result after tax for the balance sheet."""
    return _result_before_tax(data) - _cit_expense(data)


def profit_and_loss(data: Administracli) -> Panel:
    """Generate a profit-and-loss statement: revenue, costs, result before tax, CIT, net result."""
    totals = _sum_by_category(data)
    open_incoming = get_open_incoming_invoices(data)
    open_outgoing = get_open_outgoing_invoices(data)

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

    # Open outgoing invoices = revenue earned but not yet received
    debtors_total = sum(oi.balance for oi in open_outgoing)
    if debtors_total != Decimal(0):
        table.add_row("  Debtors (open invoices)", _amount_str(debtors_total), "")
        revenue_total += debtors_total

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

    # Open incoming invoices = costs incurred but not yet paid
    creditors_total = sum(oi.balance for oi in open_incoming)
    if creditors_total != Decimal(0):
        table.add_row("  Creditors (open invoices)", _amount_str(-creditors_total), "")
        costs_total -= creditors_total

    table.add_row(
        Text("Total costs", style="bold"),
        "",
        Text(_amount_str(costs_total), style="bold"),
    )

    # --- Result before tax ---
    table.add_section()
    rbt = revenue_total + costs_total
    table.add_row(
        Text("Result before tax", style="bold"),
        "",
        Text(_amount_str(rbt), style="bold"),
    )

    # --- Corporate income tax ---
    cit = _cit_expense(data)
    if data.cit_amount is not None:
        table.add_row("  Corporate income tax", _amount_str(-cit), "")

    # --- Net result after tax ---
    net = rbt - cit
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
