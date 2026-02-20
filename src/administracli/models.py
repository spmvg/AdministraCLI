from datetime import date
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import List, Optional

SystemField = Optional  # distinguish optional fields from system fields

class Categories(StrEnum):
    CAPITAL = 'capital'
    GENERAL_COSTS = 'general_costs'
    FINANCIAL_COSTS = 'financial_costs'
    FINANCIAL_REVENUE = 'financial_revenue'
    CROSS_BOOKING = 'cross_booking'
    INCOMING_INVOICE = 'incoming_invoice'
    OUTGOING_INVOICE = 'outgoing_invoice'
    VAT = 'VAT'

@dataclass
class Transaction:
    date: date
    amount: Decimal
    bank_account: str
    description: Optional[str]
    _id: SystemField[str]
    _incoming_invoice_id: SystemField[str]
    _outgoing_invoice_id: SystemField[str]
    _category: SystemField[str]

@dataclass
class Invoice:
    date: date
    amount: Decimal
    counterparty: str
    _id: SystemField[str]
    _vat_rate: SystemField[Decimal]

@dataclass
class IncomingInvoice(Invoice):
    pass

@dataclass
class OutgoingInvoice(Invoice):
    pass

@dataclass
class Administracli:
    transactions: List[Transaction]
    incoming_invoices: List[IncomingInvoice]
    outgoing_invoices: List[OutgoingInvoice]