import os
import tempfile
import unittest
from datetime import date
from decimal import Decimal

from administracli.closing import get_total_vat_position, get_open_incoming_invoices, get_open_outgoing_invoices
from administracli.excel_io import init_workbook, load_workbook, save_workbook
from administracli.models import (
    IncomingInvoice,
    OutgoingInvoice,
    VATDeclaration,
)
from administracli.reports import (
    _sum_by_bank_account,
    _cit_advances,
    _net_result,
)


class TestVATComputation(unittest.TestCase):
    """Round-trip test: create workbook, add invoices + declaration, save, reload, verify."""

    def setUp(self):
        self.path = os.path.join(tempfile.gettempdir(), "test_vat.xlsx")
        init_workbook(self.path)
        data = load_workbook(self.path)

        data.incoming_invoices.append(IncomingInvoice(
            date=date(2026, 1, 15), amount=Decimal("121"),
            counterparty="Dom", _id="i1", vat_rate=Decimal("0.21"),
        ))
        data.incoming_invoices.append(IncomingInvoice(
            date=date(2026, 1, 20), amount=Decimal("200"),
            counterparty="US", _id="i2",
            vat_rate_abroad_from_outside_eu=Decimal("0.21"),
        ))
        data.incoming_invoices.append(IncomingInvoice(
            date=date(2026, 2, 1), amount=Decimal("150"),
            counterparty="EU", _id="i3",
            vat_rate_abroad_from_inside_eu=Decimal("0.21"),
        ))
        data.outgoing_invoices.append(OutgoingInvoice(
            date=date(2026, 1, 10), amount=Decimal("363"),
            counterparty="Cust", _id="o1", vat_rate=Decimal("0.21"),
        ))
        data.vat_declarations.append(VATDeclaration(
            period_start_date_inclusive=date(2026, 1, 1),
            period_end_date_exclusive=date(2026, 4, 1),
            _revenue_ex_vat=None, _revenue_vat=None,
            _reverse_charge_outside_eu_ex_vat=None,
            _reverse_charge_outside_eu_vat=None,
            _reverse_charge_inside_eu_ex_vat=None,
            _reverse_charge_inside_eu_vat=None,
            _input_vat=None, _id="v1",
        ))

        save_workbook(self.path, data)
        self.data = load_workbook(self.path)
        self.decl = self.data.vat_declarations[0]

    def tearDown(self):
        os.remove(self.path)

    # -- revenue (outgoing invoice 363 incl 21% VAT) --

    def test_revenue_ex_vat(self):
        self.assertEqual(self.decl._revenue_ex_vat, Decimal("300"))

    def test_revenue_vat(self):
        self.assertEqual(self.decl._revenue_vat, Decimal("63"))

    # -- reverse-charge outside EU (200 incl 21%) --

    def test_reverse_charge_outside_eu_ex_vat(self):
        self.assertEqual(self.decl._reverse_charge_outside_eu_ex_vat, Decimal("165"))

    def test_reverse_charge_outside_eu_vat(self):
        self.assertEqual(self.decl._reverse_charge_outside_eu_vat, Decimal("35"))

    # -- reverse-charge inside EU (150 incl 21%) --

    def test_reverse_charge_inside_eu_ex_vat(self):
        self.assertEqual(self.decl._reverse_charge_inside_eu_ex_vat, Decimal("124"))

    def test_reverse_charge_inside_eu_vat(self):
        self.assertEqual(self.decl._reverse_charge_inside_eu_vat, Decimal("26"))

    # -- input VAT: domestic 21 + rc_outside 35 + rc_inside 26 = 82 --

    def test_input_vat(self):
        self.assertEqual(self.decl._input_vat, Decimal("82"))

    # -- net VAT position (no payments yet) --

    def test_vat_position(self):
        # owed = 63 + 35 + 26 - 82 = 42
        self.assertEqual(get_total_vat_position(self.data), Decimal("42"))

    def test_balance_sheet_balances(self):
        data = self.data
        bank = sum(_sum_by_bank_account(data).values(), Decimal(0))
        debtors = sum(oi.balance for oi in get_open_outgoing_invoices(data))
        vat_pos = get_total_vat_position(data)
        vat_receivable = -vat_pos if vat_pos < 0 else Decimal(0)
        advances = _cit_advances(data)
        cit_receivable = -advances if data.cit_amount is None else -advances - data.cit_amount
        cit_asset = cit_receivable if cit_receivable > 0 else Decimal(0)
        assets = bank + debtors + vat_receivable + cit_asset

        creditors = sum(oi.balance for oi in get_open_incoming_invoices(data))
        vat_payable = vat_pos if vat_pos > 0 else Decimal(0)
        cit_liability = -cit_receivable if cit_receivable < 0 else Decimal(0)
        equity = _net_result(data) + creditors + vat_payable + cit_liability

        self.assertEqual(assets, equity)


if __name__ == "__main__":
    unittest.main()

