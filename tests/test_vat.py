import os
import tempfile
import unittest
from datetime import date
from decimal import Decimal

from administracli.closing import get_total_vat_position
from administracli.excel_io import init_workbook, load_workbook, save_workbook
from administracli.models import (
    IncomingInvoice,
    OutgoingInvoice,
    VATDeclaration,
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


if __name__ == "__main__":
    unittest.main()

