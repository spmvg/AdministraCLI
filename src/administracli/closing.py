"""
Closing checks: determine whether the books can be closed.
"""

from dataclasses import dataclass
from decimal import Decimal

from administracli.models import (
    Administracli,
    Categories,
    IncomingInvoice,
    Invoice,
    OutgoingInvoice,
    Transaction,
)


@dataclass
class OpenInvoice:
    """An invoice with a non-zero remaining balance."""
    invoice: Invoice
    balance: Decimal  # positive = still owed


@dataclass
class ClosingStatus:
    """Result of all closing checks."""

    uncategorised: list[Transaction]

    @property
    def is_closed(self) -> bool:
        return len(self.uncategorised) == 0


def check_closing(data: Administracli) -> ClosingStatus:
    """Run all closing checks and return the status."""
    return ClosingStatus(
        uncategorised=get_uncategorised(data),
    )


def get_uncategorised(data: Administracli) -> list[Transaction]:
    """Transactions that have no _category set."""
    return [t for t in data.transactions if t._category is None]


def get_open_incoming_invoices(data: Administracli) -> list[OpenInvoice]:
    """Incoming invoices that are not fully paid.

    An incoming invoice is a cost: its amount is positive (what we owe).
    Payments are transactions with negative amount (money leaving the bank).
    Balance = invoice.amount + sum(transaction.amount for matching transactions).
    If balance > 0, we still owe money (creditor).
    """
    payment_sums: dict[str, Decimal] = {}
    for t in data.transactions:
        if t._incoming_invoice_id is not None:
            payment_sums[t._incoming_invoice_id] = (
                payment_sums.get(t._incoming_invoice_id, Decimal(0)) + t.amount
            )

    result = []
    for inv in data.incoming_invoices:
        paid = payment_sums.get(inv._id, Decimal(0))
        balance = inv.amount + paid  # paid is negative, so balance shrinks
        if balance != Decimal(0):
            result.append(OpenInvoice(invoice=inv, balance=balance))
    return result


def get_open_outgoing_invoices(data: Administracli) -> list[OpenInvoice]:
    """Outgoing invoices that are not fully paid.

    An outgoing invoice is revenue: its amount is positive (what customer owes us).
    Payments are transactions with positive amount (money entering the bank).
    Balance = invoice.amount - sum(transaction.amount for matching transactions).
    If balance > 0, customer still owes us (debtor).
    """
    payment_sums: dict[str, Decimal] = {}
    for t in data.transactions:
        if t._outgoing_invoice_id is not None:
            payment_sums[t._outgoing_invoice_id] = (
                payment_sums.get(t._outgoing_invoice_id, Decimal(0)) + t.amount
            )

    result = []
    for inv in data.outgoing_invoices:
        received = payment_sums.get(inv._id, Decimal(0))
        balance = inv.amount - received  # received is positive, so balance shrinks
        if balance != Decimal(0):
            result.append(OpenInvoice(invoice=inv, balance=balance))
    return result
