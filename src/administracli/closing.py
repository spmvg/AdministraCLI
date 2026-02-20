"""
Open invoice calculations.
"""

from dataclasses import dataclass
from decimal import Decimal

from administracli.models import Administracli, Invoice


@dataclass
class OpenInvoice:
    invoice: Invoice
    balance: Decimal


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
