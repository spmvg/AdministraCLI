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
    """Net VAT position across all declarations. Positive = owe, negative = receivable.
    Also includes unlinked VAT advances (VAT transactions without a declaration id)."""
    total = sum((_vat_owed(decl) for decl in data.vat_declarations), Decimal(0))

    # All VAT-category payments (linked or not)
    vat_payments = sum(
        (t.amount for t in data.transactions if t._category == str(Categories.VAT)),
        Decimal(0),
    )
    total += vat_payments  # payments are negative, so this reduces what we owe

    return total

