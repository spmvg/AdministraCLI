"""
Generate a demo Excel workbook for screenshots.

Creates examples/demo.xlsx with:
- Several categorised transactions  → balance sheet & P&L have values
- One uncategorised transaction     → matching screen shows on run
- Invoices and a VAT declaration    → open invoices visible in picker

Usage:
    python examples/make_demo.py
    python -m administracli run examples/demo.xlsx
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from administracli.excel_io import init_workbook, load_workbook, save_workbook
from administracli.models import (
    Categories,
    IncomingInvoice,
    OutgoingInvoice,
    Transaction,
    VATDeclaration,
)

OUT = Path(__file__).parent / "demo.xlsx"


def main() -> None:
    init_workbook(str(OUT))
    data = load_workbook(str(OUT))

    # -- invoices --
    data.outgoing_invoices.append(OutgoingInvoice(
        date=date(2026, 1, 8), amount=Decimal("1210"),
        counterparty="Acme Corp", _id="oi-1", vat_rate=Decimal("0.21"),
    ))
    data.outgoing_invoices.append(OutgoingInvoice(
        date=date(2026, 2, 3), amount=Decimal("605"),
        counterparty="Globex Ltd", _id="oi-2", vat_rate=Decimal("0.21"),
    ))
    data.incoming_invoices.append(IncomingInvoice(
        date=date(2026, 1, 12), amount=Decimal("363"),
        counterparty="Office Supplies BV", _id="ii-1", vat_rate=Decimal("0.21"),
    ))
    data.incoming_invoices.append(IncomingInvoice(
        date=date(2026, 1, 25), amount=Decimal("121"),
        counterparty="Cloud Hosting Inc", _id="ii-2",
        vat_rate_abroad_from_outside_eu=Decimal("0.21"),
    ))

    # -- VAT declaration --
    data.vat_declarations.append(VATDeclaration(
        period_start_date_inclusive=date(2026, 1, 1),
        period_end_date_exclusive=date(2026, 4, 1),
        _revenue_ex_vat=None, _revenue_vat=None,
        _reverse_charge_outside_eu_ex_vat=None,
        _reverse_charge_outside_eu_vat=None,
        _reverse_charge_inside_eu_ex_vat=None,
        _reverse_charge_inside_eu_vat=None,
        _input_vat=None, _id="vat-q1",
    ))

    bank = "NL02ABNA0123456789"

    # -- already categorised transactions --
    data.transactions += [
        # capital deposit
        Transaction(
            date=date(2026, 1, 1), amount=Decimal("5000"),
            bank_account=bank, description="Initial capital deposit",
            _id="t1", _incoming_invoice_id=None, _outgoing_invoice_id=None,
            _vat_declaration_id=None, _category=str(Categories.CAPITAL),
        ),
        # received payment for Acme invoice
        Transaction(
            date=date(2026, 1, 20), amount=Decimal("1210"),
            bank_account=bank, description="Payment from Acme Corp",
            _id="t2", _incoming_invoice_id=None, _outgoing_invoice_id="oi-1",
            _vat_declaration_id=None, _category=str(Categories.OUTGOING_INVOICE),
        ),
        # paid Office Supplies invoice
        Transaction(
            date=date(2026, 1, 28), amount=Decimal("-363"),
            bank_account=bank, description="Office Supplies BV - inv 2026-004",
            _id="t3", _incoming_invoice_id="ii-1", _outgoing_invoice_id=None,
            _vat_declaration_id=None, _category=str(Categories.INCOMING_INVOICE),
        ),
        # paid Cloud Hosting invoice
        Transaction(
            date=date(2026, 2, 1), amount=Decimal("-121"),
            bank_account=bank, description="Cloud Hosting Inc - monthly",
            _id="t4", _incoming_invoice_id="ii-2", _outgoing_invoice_id=None,
            _vat_declaration_id=None, _category=str(Categories.INCOMING_INVOICE),
        ),
        # bank fees
        Transaction(
            date=date(2026, 2, 5), amount=Decimal("-8.50"),
            bank_account=bank, description="Bank fees Q1",
            _id="t5", _incoming_invoice_id=None, _outgoing_invoice_id=None,
            _vat_declaration_id=None, _category=str(Categories.FINANCIAL_COSTS),
        ),
    ]

    # -- one uncategorised transaction (screenshot: matching screen) --
    data.transactions.append(Transaction(
        date=date(2026, 2, 10), amount=Decimal("605"),
        bank_account=bank, description="Payment from Globex Ltd",
        _id="t6", _incoming_invoice_id=None, _outgoing_invoice_id=None,
        _vat_declaration_id=None, _category=None,
    ))

    save_workbook(str(OUT), data)
    print(f"Created {OUT}")


if __name__ == "__main__":
    main()

