# AdministraCLI

Minimal transaction-matching and invoicing tool for small businesses.
All data lives in a single local Excel file — no server, no database.

TODO: image

AdministraCLI is **not** a full accounting package. It tracks bank transactions and invoices only — no fixed assets, loans, or depreciation. Create a separate workbook for each reporting year. Because you only enter mutations (bank transactions and invoices), the generated balance sheet shows **differences**, not absolute positions. If your situation requires a complete balance sheet, use AdministraCLI's output as input for one you maintain yourself.

## Installation

```bash
pip install administracli
```

## Usage

```bash
python -m administracli init          # create administracli.xlsx
# fill in your transactions and invoices in Excel
python -m administracli run           # categorise and view reports
```

`run` walks you through each uncategorised transaction.
Open invoices are shown alongside categories so you can match them in one step.
Once everything is categorised, the balance sheet and profit-and-loss statement are shown.

## Corporate income tax

Corporate income tax (CIT) advance payments are categorised as `Corporate income tax` like any other transaction.
The definitive CIT amount can be set in the `settings` sheet (`cit_amount`).

- **Not yet assessed**: advances show as *CIT prepayment* on the balance sheet. Nothing appears in the P&L.
- **Assessed**: the definitive amount appears as tax expense in the P&L. The difference between advances paid and the definitive amount shows as *CIT receivable* (overpaid) or *CIT payable* (underpaid) on the balance sheet.

## VAT

Add VAT periods in the `vat_declarations` sheet (start date inclusive, end date exclusive).
Computed fields are recalculated on every run. Amounts are rounded to whole euros (Dutch BTW).

Each **outgoing invoice** requires `vat_rate`. Each **incoming invoice** requires exactly one of:
`vat_rate`, `vat_rate_abroad_from_outside_eu`, or `vat_rate_abroad_from_inside_eu`.
All invoice amounts are **including VAT**.

Categorise VAT advance payments as `VAT`. Link a transaction to a VAT declaration for definitive payments.
