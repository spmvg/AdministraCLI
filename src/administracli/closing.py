"""
Closing checks: determine whether the books can be closed.
"""

from dataclasses import dataclass

from administracli.models import (
    Administracli,
    Categories,
    IncomingInvoice,
    OutgoingInvoice,
    Transaction,
)


@dataclass
class ClosingStatus:
    """Result of all closing checks."""

    uncategorised: list[Transaction]
    unmatched_incoming: list[Transaction]
    unmatched_outgoing: list[Transaction]
    unreferenced_incoming: list[IncomingInvoice]
    unreferenced_outgoing: list[OutgoingInvoice]

    @property
    def is_closed(self) -> bool:
        return (
            len(self.uncategorised) == 0
            and len(self.unmatched_incoming) == 0
            and len(self.unmatched_outgoing) == 0
            and len(self.unreferenced_incoming) == 0
            and len(self.unreferenced_outgoing) == 0
        )


def check_closing(data: Administracli) -> ClosingStatus:
    """Run all closing checks and return the status."""
    return ClosingStatus(
        uncategorised=get_uncategorised(data),
        unmatched_incoming=get_unmatched_incoming(data),
        unmatched_outgoing=get_unmatched_outgoing(data),
        unreferenced_incoming=get_unreferenced_incoming(data),
        unreferenced_outgoing=get_unreferenced_outgoing(data),
    )


def get_uncategorised(data: Administracli) -> list[Transaction]:
    """Transactions that have no _category set."""
    return [t for t in data.transactions if t._category is None]


def get_unmatched_incoming(data: Administracli) -> list[Transaction]:
    """Transactions with category incoming_invoice but no valid _incoming_invoice_id."""
    incoming_ids = {inv._id for inv in data.incoming_invoices}
    return [
        t for t in data.transactions
        if t._category == Categories.INCOMING_INVOICE
        and (t._incoming_invoice_id is None or t._incoming_invoice_id not in incoming_ids)
    ]


def get_unmatched_outgoing(data: Administracli) -> list[Transaction]:
    """Transactions with category outgoing_invoice but no valid _outgoing_invoice_id."""
    outgoing_ids = {inv._id for inv in data.outgoing_invoices}
    return [
        t for t in data.transactions
        if t._category == Categories.OUTGOING_INVOICE
        and (t._outgoing_invoice_id is None or t._outgoing_invoice_id not in outgoing_ids)
    ]


def get_unreferenced_incoming(data: Administracli) -> list[IncomingInvoice]:
    """Incoming invoices not referenced by any transaction."""
    referenced_ids = {
        t._incoming_invoice_id for t in data.transactions
        if t._incoming_invoice_id is not None
    }
    return [inv for inv in data.incoming_invoices if inv._id not in referenced_ids]


def get_unreferenced_outgoing(data: Administracli) -> list[OutgoingInvoice]:
    """Outgoing invoices not referenced by any transaction."""
    referenced_ids = {
        t._outgoing_invoice_id for t in data.transactions
        if t._outgoing_invoice_id is not None
    }
    return [inv for inv in data.outgoing_invoices if inv._id not in referenced_ids]
