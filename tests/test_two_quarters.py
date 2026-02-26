"""
End-to-end test: two consecutive VAT quarters with domestic, inside-EU
reverse-charge, and outside-EU reverse-charge invoices.

Q1 (2026-01-01 to 2026-04-01):
  - Outgoing invoice: 363 incl 21% VAT to Customer A
  - Incoming domestic: 121 incl 21% VAT from Supplier NL
  - Incoming outside-EU RC: 200 ex-VAT, 21% from Supplier US
  - VAT advance payment of 30

Q2 (2026-04-01 to 2026-07-01):
  - Outgoing invoice: 726 incl 21% VAT to Customer B
  - Incoming inside-EU RC: 400 ex-VAT, 21% from Supplier DE
  - Incoming domestic: 60.50 incl 21% VAT from Supplier NL2
  - Definitive Q1 VAT payment of 12 (linked to declaration)
"""

import os
import tempfile
import unittest
from datetime import date
from decimal import Decimal

from administracli.closing import (
    compute_revenue_vat,
    compute_domestic_input_vat,
    compute_total_vat_owed,
    get_total_vat_position,
    get_open_incoming_invoices,
    get_open_outgoing_invoices,
)
from administracli.excel_io import init_workbook, load_workbook, save_workbook
from administracli.models import (
    Categories,
    IncomingInvoice,
    OutgoingInvoice,
    Transaction,
    VATDeclaration,
)
from administracli.reports import (
    _sum_by_bank_account,
    _sum_by_category,
    _cit_advances,
    _net_result,
)

BANK = "NL99TEST0000000001"


class TestTwoQuarters(unittest.TestCase):
    """Two consecutive VAT quarters with domestic, inside-EU RC, and outside-EU RC invoices."""

    def setUp(self):
        self.path = os.path.join(tempfile.gettempdir(), "test_two_quarters.xlsx")
        init_workbook(self.path)
        data = load_workbook(self.path)

        # ── Q1 invoices ──
        data.outgoing_invoices.append(OutgoingInvoice(
            date=date(2026, 1, 10), amount=Decimal("363"),
            counterparty="Customer A", _id="o1", vat_rate=Decimal("0.21"),
        ))
        data.incoming_invoices.append(IncomingInvoice(
            date=date(2026, 1, 15), amount=Decimal("121"),
            counterparty="Supplier NL", _id="i1", vat_rate=Decimal("0.21"),
        ))
        data.incoming_invoices.append(IncomingInvoice(
            date=date(2026, 1, 20), amount=Decimal("200"),
            counterparty="Supplier US", _id="i2",
            vat_rate_abroad_from_outside_eu=Decimal("0.21"),
        ))

        # ── Q2 invoices ──
        data.outgoing_invoices.append(OutgoingInvoice(
            date=date(2026, 4, 5), amount=Decimal("726"),
            counterparty="Customer B", _id="o2", vat_rate=Decimal("0.21"),
        ))
        data.incoming_invoices.append(IncomingInvoice(
            date=date(2026, 4, 12), amount=Decimal("400"),
            counterparty="Supplier DE", _id="i3",
            vat_rate_abroad_from_inside_eu=Decimal("0.21"),
        ))
        data.incoming_invoices.append(IncomingInvoice(
            date=date(2026, 5, 1), amount=Decimal("60.50"),
            counterparty="Supplier NL2", _id="i4", vat_rate=Decimal("0.21"),
        ))

        # ── VAT declarations ──
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
        data.vat_declarations.append(VATDeclaration(
            period_start_date_inclusive=date(2026, 4, 1),
            period_end_date_exclusive=date(2026, 7, 1),
            _revenue_ex_vat=None, _revenue_vat=None,
            _reverse_charge_outside_eu_ex_vat=None,
            _reverse_charge_outside_eu_vat=None,
            _reverse_charge_inside_eu_ex_vat=None,
            _reverse_charge_inside_eu_vat=None,
            _input_vat=None, _id="v2",
        ))

        # ── Transactions ──
        data.transactions += [
            # Capital
            Transaction(
                date=date(2026, 1, 1), amount=Decimal("10000"),
                bank_account=BANK, description="Capital deposit",
                _id="t1", _incoming_invoice_id=None, _outgoing_invoice_id=None,
                _vat_declaration_id=None, _category=str(Categories.CAPITAL),
            ),
            # Received from Customer A
            Transaction(
                date=date(2026, 1, 25), amount=Decimal("363"),
                bank_account=BANK, description="Customer A payment",
                _id="t2", _incoming_invoice_id=None, _outgoing_invoice_id="o1",
                _vat_declaration_id=None, _category=str(Categories.OUTGOING_INVOICE),
            ),
            # Paid Supplier NL (domestic)
            Transaction(
                date=date(2026, 2, 1), amount=Decimal("-121"),
                bank_account=BANK, description="Supplier NL inv",
                _id="t3", _incoming_invoice_id="i1", _outgoing_invoice_id=None,
                _vat_declaration_id=None, _category=str(Categories.INCOMING_INVOICE),
            ),
            # Paid Supplier US (outside-EU RC)
            Transaction(
                date=date(2026, 2, 5), amount=Decimal("-200"),
                bank_account=BANK, description="Supplier US inv",
                _id="t4", _incoming_invoice_id="i2", _outgoing_invoice_id=None,
                _vat_declaration_id=None, _category=str(Categories.INCOMING_INVOICE),
            ),
            # Q1 VAT advance
            Transaction(
                date=date(2026, 3, 15), amount=Decimal("-30"),
                bank_account=BANK, description="VAT advance Q1",
                _id="t5", _incoming_invoice_id=None, _outgoing_invoice_id=None,
                _vat_declaration_id=None, _category=str(Categories.VAT),
            ),
            # Received from Customer B
            Transaction(
                date=date(2026, 4, 20), amount=Decimal("726"),
                bank_account=BANK, description="Customer B payment",
                _id="t6", _incoming_invoice_id=None, _outgoing_invoice_id="o2",
                _vat_declaration_id=None, _category=str(Categories.OUTGOING_INVOICE),
            ),
            # Paid Supplier DE (inside-EU RC)
            Transaction(
                date=date(2026, 4, 25), amount=Decimal("-400"),
                bank_account=BANK, description="Supplier DE inv",
                _id="t7", _incoming_invoice_id="i3", _outgoing_invoice_id=None,
                _vat_declaration_id=None, _category=str(Categories.INCOMING_INVOICE),
            ),
            # Paid Supplier NL2 (domestic, Q2)
            Transaction(
                date=date(2026, 5, 10), amount=Decimal("-60.50"),
                bank_account=BANK, description="Supplier NL2 inv",
                _id="t8", _incoming_invoice_id="i4", _outgoing_invoice_id=None,
                _vat_declaration_id=None, _category=str(Categories.INCOMING_INVOICE),
            ),
            # Definitive Q1 VAT payment (linked)
            Transaction(
                date=date(2026, 4, 30), amount=Decimal("-12"),
                bank_account=BANK, description="VAT definitive Q1",
                _id="t9", _incoming_invoice_id=None, _outgoing_invoice_id=None,
                _vat_declaration_id="v1", _category=str(Categories.VAT),
            ),
        ]

        save_workbook(self.path, data)
        self.data = load_workbook(self.path)
        self.q1 = self.data.vat_declarations[0]
        self.q2 = self.data.vat_declarations[1]

    def tearDown(self):
        os.remove(self.path)

    # ── Q1 declaration fields ──

    def test_q1_revenue_ex_vat(self):
        # 363 / 1.21 = 300
        self.assertEqual(self.q1._revenue_ex_vat, Decimal("300"))

    def test_q1_revenue_vat(self):
        # 363 - 300 = 63
        self.assertEqual(self.q1._revenue_vat, Decimal("63"))

    def test_q1_rc_outside_eu_ex_vat(self):
        # 200 (already ex-VAT)
        self.assertEqual(self.q1._reverse_charge_outside_eu_ex_vat, Decimal("200"))

    def test_q1_rc_outside_eu_vat(self):
        # 200 * 0.21 = 42
        self.assertEqual(self.q1._reverse_charge_outside_eu_vat, Decimal("42"))

    def test_q1_rc_inside_eu_ex_vat(self):
        # No inside-EU invoices in Q1
        self.assertEqual(self.q1._reverse_charge_inside_eu_ex_vat, Decimal("0"))

    def test_q1_rc_inside_eu_vat(self):
        self.assertEqual(self.q1._reverse_charge_inside_eu_vat, Decimal("0"))

    def test_q1_input_vat(self):
        # domestic: 121 - 121/1.21 = 21, plus RC outside: 42 → 63
        self.assertEqual(self.q1._input_vat, Decimal("63"))

    # ── Q2 declaration fields ──

    def test_q2_revenue_ex_vat(self):
        # 726 / 1.21 = 600
        self.assertEqual(self.q2._revenue_ex_vat, Decimal("600"))

    def test_q2_revenue_vat(self):
        # 726 - 600 = 126
        self.assertEqual(self.q2._revenue_vat, Decimal("126"))

    def test_q2_rc_outside_eu_ex_vat(self):
        # No outside-EU invoices in Q2
        self.assertEqual(self.q2._reverse_charge_outside_eu_ex_vat, Decimal("0"))

    def test_q2_rc_outside_eu_vat(self):
        self.assertEqual(self.q2._reverse_charge_outside_eu_vat, Decimal("0"))

    def test_q2_rc_inside_eu_ex_vat(self):
        # 400 (already ex-VAT)
        self.assertEqual(self.q2._reverse_charge_inside_eu_ex_vat, Decimal("400"))

    def test_q2_rc_inside_eu_vat(self):
        # 400 * 0.21 = 84
        self.assertEqual(self.q2._reverse_charge_inside_eu_vat, Decimal("84"))

    def test_q2_input_vat(self):
        # domestic: 60.50 - 60.50/1.21 = 10.5 → 10 (rounded), plus RC inside: 84 → 94
        # Actually: 60.50 - 50 = 10.5, total = 10.5 + 84 = 94.5 → 94
        self.assertEqual(self.q2._input_vat, Decimal("94"))

    # ── Invoice-based totals (across both quarters) ──

    def test_total_revenue_vat(self):
        # Q1: 63 + Q2: 126 = 189
        self.assertEqual(compute_revenue_vat(self.data), Decimal("189"))

    def test_total_domestic_input_vat(self):
        # Q1 domestic: 21 + Q2 domestic: 10.50 = 31.50
        self.assertEqual(compute_domestic_input_vat(self.data), Decimal("31.50"))

    def test_total_vat_owed(self):
        # revenue_vat(189) - domestic_input_vat(31.50) = 157.50
        self.assertEqual(compute_total_vat_owed(self.data), Decimal("157.50"))

    def test_total_vat_position(self):
        # owed(157.50) + payments(-30 - 12 = -42) = 115.50
        self.assertEqual(get_total_vat_position(self.data), Decimal("115.50"))

    # ── All invoices are fully paid → no open invoices ──

    def test_no_open_incoming_invoices(self):
        self.assertEqual(get_open_incoming_invoices(self.data), [])

    def test_no_open_outgoing_invoices(self):
        self.assertEqual(get_open_outgoing_invoices(self.data), [])

    # ── Bank balance ──

    def test_bank_balance(self):
        # 10000 + 363 - 121 - 200 - 30 + 726 - 400 - 60.50 - 12 = 10265.50
        bank = sum(_sum_by_bank_account(self.data).values(), Decimal(0))
        self.assertEqual(bank, Decimal("10265.50"))

    # ── Balance sheet balances ──

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

        totals = _sum_by_category(data)
        capital = totals.get(str(Categories.CAPITAL), Decimal(0))
        creditors = sum(oi.balance for oi in get_open_incoming_invoices(data))
        vat_payable = vat_pos if vat_pos > 0 else Decimal(0)
        cit_liability = -cit_receivable if cit_receivable < 0 else Decimal(0)
        equity = capital + _net_result(data) + creditors + vat_payable + cit_liability

        self.assertEqual(assets, equity)


if __name__ == "__main__":
    unittest.main()



