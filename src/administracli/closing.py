"""
Open invoice and VAT calculations.
"""

from dataclasses import dataclass
from decimal import Decimal

from administracli.models import Administracli, Categories, Invoice, VATDeclaration


@dataclass
class OpenInvoice:
    invoice: Invoice
    balance: Decimal


@dataclass
class OpenVATDeclaration:
    declaration: VATDeclaration
    owed: Decimal      # VAT owed to tax authority for this period
    paid: Decimal      # sum of VAT-category transactions linked to this declaration
    balance: Decimal   # owed - paid (positive = still owe, negative = overpaid)


def get_open_incoming_invoices(data: Administracli) -> list[OpenInvoice]:
    """Incoming invoices not fully paid (creditors)."""
    paid: dict[str, Decimal] = {}
    for t in data.transactions:
        if t._incoming_invoice_id is not None:
            paid[t._incoming_invoice_id] = paid.get(t._incoming_invoice_id, Decimal(0)) + t.amount

    return [
        OpenInvoice(invoice=inv, balance=inv.amount + paid.get(inv._id, Decimal(0)))
        for inv in data.incoming_invoices
        if inv.amount + paid.get(inv._id, Decimal(0)) != Decimal(0)
    ]


def get_open_outgoing_invoices(data: Administracli) -> list[OpenInvoice]:
    """Outgoing invoices not fully paid (debtors)."""
    received: dict[str, Decimal] = {}
    for t in data.transactions:
        if t._outgoing_invoice_id is not None:
            received[t._outgoing_invoice_id] = received.get(t._outgoing_invoice_id, Decimal(0)) + t.amount

    return [
        OpenInvoice(invoice=inv, balance=inv.amount - received.get(inv._id, Decimal(0)))
        for inv in data.outgoing_invoices
        if inv.amount - received.get(inv._id, Decimal(0)) != Decimal(0)
    ]


# ---------------------------------------------------------------------------
# Invoice-based VAT totals (independent of VAT declarations)
# ---------------------------------------------------------------------------

def compute_revenue_vat(data: Administracli) -> Decimal:
    """VAT on outgoing invoices (revenue). Amounts are incl. VAT."""
    total = Decimal(0)
    for inv in data.outgoing_invoices:
        rate = inv.vat_rate
        if rate:
            total += inv.amount - inv.amount / (1 + rate)
    return total


def compute_domestic_input_vat(data: Administracli) -> Decimal:
    """Input VAT from domestic incoming invoices only. Amounts are incl. VAT."""
    total = Decimal(0)
    for inv in data.incoming_invoices:
        if inv.vat_rate_abroad_from_outside_eu is not None:
            continue
        if inv.vat_rate_abroad_from_inside_eu is not None:
            continue
        rate = inv.vat_rate
        if rate:
            total += inv.amount - inv.amount / (1 + rate)
    return total


def compute_reverse_charge_vat(data: Administracli) -> Decimal:
    """VAT from reverse-charge invoices (both owed and deductible, net zero).

    Reverse-charge invoice amounts are ex-VAT, so VAT = amount * rate.
    """
    total = Decimal(0)
    for inv in data.incoming_invoices:
        if inv.vat_rate_abroad_from_outside_eu is not None:
            rate = inv.vat_rate_abroad_from_outside_eu
            if rate:
                total += inv.amount * rate
        elif inv.vat_rate_abroad_from_inside_eu is not None:
            rate = inv.vat_rate_abroad_from_inside_eu
            if rate:
                total += inv.amount * rate
    return total


def compute_total_vat_owed(data: Administracli) -> Decimal:
    """Total VAT owed from all invoices (before payments).

    owed = revenue VAT + reverse-charge VAT - (domestic input VAT + reverse-charge VAT)
         = revenue VAT - domestic input VAT
    """
    return compute_revenue_vat(data) - compute_domestic_input_vat(data)


# ---------------------------------------------------------------------------
# Declaration-level helpers (for declaration worksheet display)
# ---------------------------------------------------------------------------

def _vat_owed(decl: VATDeclaration) -> Decimal:
    """Net VAT owed for a single declaration period.

    owed = revenue VAT
         + reverse-charge VAT (outside EU + inside EU)  -- you owe this ...
         - input VAT                                     -- ... but deduct this
    """
    revenue_vat = decl._revenue_vat or Decimal(0)
    rc_outside = decl._reverse_charge_outside_eu_vat or Decimal(0)
    rc_inside = decl._reverse_charge_inside_eu_vat or Decimal(0)
    input_vat = decl._input_vat or Decimal(0)
    return revenue_vat + rc_outside + rc_inside - input_vat


def get_open_vat_declarations(data: Administracli) -> list[OpenVATDeclaration]:
    """VAT declarations with outstanding balance (owed ≠ paid)."""
    paid_per_decl: dict[str, Decimal] = {}
    for t in data.transactions:
        if t._category == str(Categories.VAT) and t._vat_declaration_id is not None:
            paid_per_decl[t._vat_declaration_id] = paid_per_decl.get(t._vat_declaration_id, Decimal(0)) + t.amount

    result = []
    for decl in data.vat_declarations:
        owed = _vat_owed(decl)
        paid = paid_per_decl.get(decl._id, Decimal(0))  # negative = money out
        balance = owed + paid  # positive = still owe, because paid is negative

        if balance != Decimal(0):
            result.append(OpenVATDeclaration(declaration=decl, owed=owed, paid=paid, balance=balance))
    return result


def get_total_vat_position(data: Administracli) -> Decimal:
    """Net VAT position: total owed from invoices + all VAT payments.

    Computed from invoices directly so it works with or without declarations.
    Positive = owe, negative = receivable.
    """
    total = compute_total_vat_owed(data)

    # All VAT-category payments (linked or not)
    vat_payments = sum(
        (t.amount for t in data.transactions if t._category == str(Categories.VAT)),
        Decimal(0),
    )
    total += vat_payments  # payments are negative, so this reduces what we owe

    return total

