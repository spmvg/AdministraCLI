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
    _vat_declaration_id: SystemField[str]
    _category: SystemField[str]

@dataclass
class Invoice:
    date: date
    amount: Decimal
    counterparty: str
    _id: SystemField[str]

@dataclass
class IncomingInvoice(Invoice):
    vat_rate: Optional[Decimal] = None
    vat_rate_abroad_from_outside_eu: Optional[Decimal] = None
    vat_rate_abroad_from_inside_eu: Optional[Decimal] = None

@dataclass
class OutgoingInvoice(Invoice):
    vat_rate: Decimal

@dataclass
class VATDeclaration:
    period_start_date_inclusive: date
    period_end_date_exclusive: date
    # Outgoing invoices (revenue)
    _revenue_ex_vat: SystemField[Decimal]
    _revenue_vat: SystemField[Decimal]
    # Incoming invoices from abroad (reverse-charge / verlegde BTW)
    _reverse_charge_outside_eu_ex_vat: SystemField[Decimal]
    _reverse_charge_outside_eu_vat: SystemField[Decimal]
    _reverse_charge_inside_eu_ex_vat: SystemField[Decimal]
    _reverse_charge_inside_eu_vat: SystemField[Decimal]
    # Input VAT (deductible, from domestic incoming invoices + reverse-charge)
    _input_vat: SystemField[Decimal]
    _id: SystemField[str]

@dataclass
class Administracli:
    transactions: List[Transaction]
    incoming_invoices: List[IncomingInvoice]
    outgoing_invoices: List[OutgoingInvoice]
    vat_declarations: List[VATDeclaration] = None
    cit_amount: Optional[Decimal] = None  # definitive corporate income tax; None = not yet assessed

    def __post_init__(self):
        if self.vat_declarations is None:
            self.vat_declarations = []

