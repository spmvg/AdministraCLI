"""
Read and write the AdministraCLI Excel workbook.
"""

import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

import openpyxl
import pandas as pd

from administracli.models import (
    Administracli,
    IncomingInvoice,
    OutgoingInvoice,
    Transaction,
)

TRANSACTIONS_SHEET = "transactions"
INCOMING_INVOICES_SHEET = "incoming_invoices"
OUTGOING_INVOICES_SHEET = "outgoing_invoices"
SETTINGS_SHEET = "settings"

TRANSACTION_COLUMNS = [
    "Date",
    "Amount",
    "Bank Account",
    "Description",
    "_id",
    "_incoming_invoice_id",
    "_outgoing_invoice_id",
    "_category",
]

INCOMING_INVOICE_COLUMNS = [
    "Date",
    "Amount",
    "Counterparty",
    "_id",
    "_vat_rate",
]

OUTGOING_INVOICE_COLUMNS = [
    "Date",
    "Amount",
    "Counterparty",
    "_id",
    "_vat_rate",
]


def _generate_id() -> str:
    return str(uuid.uuid4())


def _to_optional_str(value) -> Optional[str]:
    if pd.isna(value):
        return None
    return str(value)


def _to_optional_decimal(value) -> Optional[Decimal]:
    if pd.isna(value):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def init_workbook(path: str) -> None:
    """Create a new Excel workbook with empty worksheets and correct headers."""
    wb = openpyxl.Workbook()

    # Remove default sheet
    ws = wb.active
    wb.remove(ws)

    for sheet_name, columns in [
        (TRANSACTIONS_SHEET, TRANSACTION_COLUMNS),
        (INCOMING_INVOICES_SHEET, INCOMING_INVOICE_COLUMNS),
        (OUTGOING_INVOICES_SHEET, OUTGOING_INVOICE_COLUMNS),
    ]:
        ws = wb.create_sheet(title=sheet_name)
        for col_idx, col_name in enumerate(columns, start=1):
            ws.cell(row=1, column=col_idx, value=col_name)

    # Settings sheet (key-value pairs)
    ws = wb.create_sheet(title=SETTINGS_SHEET)
    ws.cell(row=1, column=1, value="Key")
    ws.cell(row=1, column=2, value="Value")
    ws.cell(row=2, column=1, value="cit_amount")
    ws.cell(row=2, column=2, value=None)

    wb.save(path)


def load_workbook(path: str) -> Administracli:
    """Load an AdministraCLI workbook into dataclass instances."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Workbook not found: {path}")

    transactions = _load_transactions(path)
    incoming_invoices = _load_incoming_invoices(path)
    outgoing_invoices = _load_outgoing_invoices(path)
    cit_amount = _load_cit_amount(path)

    return Administracli(
        transactions=transactions,
        incoming_invoices=incoming_invoices,
        outgoing_invoices=outgoing_invoices,
        cit_amount=cit_amount,
    )


def _read_sheet(path: str, sheet_name: str, expected_columns: list[str]) -> pd.DataFrame:
    """Read a sheet, returning an empty DataFrame with expected columns if the sheet is empty."""
    try:
        df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
    except ValueError:
        # Sheet doesn't exist
        df = pd.DataFrame(columns=expected_columns)

    for col in expected_columns:
        if col not in df.columns:
            df[col] = None

    return df


def _load_cit_amount(path: str) -> Optional[Decimal]:
    """Load the definitive corporate income tax amount from the settings sheet."""
    try:
        df = pd.read_excel(path, sheet_name=SETTINGS_SHEET, engine="openpyxl")
    except ValueError:
        return None
    row = df.loc[df["Key"] == "cit_amount"]
    if row.empty:
        return None
    val = row.iloc[0]["Value"]
    if pd.isna(val):
        return None
    try:
        return Decimal(str(val))
    except InvalidOperation:
        return None


def _load_transactions(path: str) -> list[Transaction]:
    df = _read_sheet(path, TRANSACTIONS_SHEET, TRANSACTION_COLUMNS)
    transactions = []
    for _, row in df.iterrows():
        _id = _to_optional_str(row.get("_id"))
        if _id is None:
            _id = _generate_id()

        transactions.append(
            Transaction(
                date=row["Date"] if not pd.isna(row.get("Date")) else None,
                amount=Decimal(str(row["Amount"])) if not pd.isna(row.get("Amount")) else Decimal(0),
                bank_account=str(row["Bank Account"]) if not pd.isna(row.get("Bank Account")) else "",
                description=_to_optional_str(row.get("Description")),
                _id=_id,
                _incoming_invoice_id=_to_optional_str(row.get("_incoming_invoice_id")),
                _outgoing_invoice_id=_to_optional_str(row.get("_outgoing_invoice_id")),
                _category=_to_optional_str(row.get("_category")),
            )
        )
    return transactions


def _load_invoices(path: str, sheet_name: str, expected_columns: list[str]):
    df = _read_sheet(path, sheet_name, expected_columns)
    invoices = []
    for _, row in df.iterrows():
        _id = _to_optional_str(row.get("_id"))
        if _id is None:
            _id = _generate_id()

        invoices.append(
            dict(
                date=row["Date"] if not pd.isna(row.get("Date")) else None,
                amount=Decimal(str(row["Amount"])) if not pd.isna(row.get("Amount")) else Decimal(0),
                counterparty=str(row["Counterparty"]) if not pd.isna(row.get("Counterparty")) else "",
                _id=_id,
                _vat_rate=_to_optional_decimal(row.get("_vat_rate")),
            )
        )
    return invoices


def _load_incoming_invoices(path: str) -> list[IncomingInvoice]:
    raw = _load_invoices(path, INCOMING_INVOICES_SHEET, INCOMING_INVOICE_COLUMNS)
    return [IncomingInvoice(**r) for r in raw]


def _load_outgoing_invoices(path: str) -> list[OutgoingInvoice]:
    raw = _load_invoices(path, OUTGOING_INVOICES_SHEET, OUTGOING_INVOICE_COLUMNS)
    return [OutgoingInvoice(**r) for r in raw]


def save_workbook(path: str, data: Administracli) -> None:
    """Write the Administracli data back to the Excel workbook."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    _write_transactions(wb, data.transactions)
    _write_invoices(wb, INCOMING_INVOICES_SHEET, INCOMING_INVOICE_COLUMNS, data.incoming_invoices)
    _write_invoices(wb, OUTGOING_INVOICES_SHEET, OUTGOING_INVOICE_COLUMNS, data.outgoing_invoices)
    _write_settings(wb, data)

    wb.save(path)


def _write_transactions(wb: openpyxl.Workbook, transactions: list[Transaction]) -> None:
    ws = wb.create_sheet(title=TRANSACTIONS_SHEET)
    for col_idx, col_name in enumerate(TRANSACTION_COLUMNS, start=1):
        ws.cell(row=1, column=col_idx, value=col_name)

    field_map = {
        "Date": "date",
        "Amount": "amount",
        "Bank Account": "bank_account",
        "Description": "description",
        "_id": "_id",
        "_incoming_invoice_id": "_incoming_invoice_id",
        "_outgoing_invoice_id": "_outgoing_invoice_id",
        "_category": "_category",
    }

    for row_idx, txn in enumerate(transactions, start=2):
        for col_idx, col_name in enumerate(TRANSACTION_COLUMNS, start=1):
            attr = field_map[col_name]
            value = getattr(txn, attr)
            if isinstance(value, Decimal):
                value = float(value)
            ws.cell(row=row_idx, column=col_idx, value=value)


def _write_invoices(wb: openpyxl.Workbook, sheet_name: str, columns: list[str], invoices) -> None:
    ws = wb.create_sheet(title=sheet_name)
    for col_idx, col_name in enumerate(columns, start=1):
        ws.cell(row=1, column=col_idx, value=col_name)

    field_map = {
        "Date": "date",
        "Amount": "amount",
        "Counterparty": "counterparty",
        "_id": "_id",
        "_vat_rate": "_vat_rate",
    }

    for row_idx, inv in enumerate(invoices, start=2):
        for col_idx, col_name in enumerate(columns, start=1):
            attr = field_map[col_name]
            value = getattr(inv, attr)
            if isinstance(value, Decimal):
                value = float(value)
            ws.cell(row=row_idx, column=col_idx, value=value)


def _write_settings(wb: openpyxl.Workbook, data: Administracli) -> None:
    ws = wb.create_sheet(title=SETTINGS_SHEET)
    ws.cell(row=1, column=1, value="Key")
    ws.cell(row=1, column=2, value="Value")
    ws.cell(row=2, column=1, value="cit_amount")
    ws.cell(row=2, column=2, value=float(data.cit_amount) if data.cit_amount is not None else None)

