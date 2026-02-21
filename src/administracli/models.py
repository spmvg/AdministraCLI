from datetime import date
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import List, Optional

SystemField = Optional  # distinguish optional fields from system fields

class Categories(StrEnum):
    CAPITAL = 'Capital'
    GENERAL_COSTS = 'General costs'
    FINANCIAL_COSTS = 'Financial costs'
    FINANCIAL_REVENUE = 'Financial revenue'
    CROSS_BOOKING = 'Cross booking'
    INCOMING_INVOICE = 'Incoming invoice'
    OUTGOING_INVOICE = 'Outgoing invoice'
    VAT = 'VAT'
    CORPORATE_INCOME_TAX = 'Corporate income tax'

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
    cit_amount: Optional[Decimal] = None  # definitive corporate income tax; None = not yet assessed
