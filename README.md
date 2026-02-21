# AdministraCLI

Command line tool for small business administration with local data in an Excel sheet.

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

CIT advance payments are categorised as `Corporate income tax` like any other transaction.
The definitive CIT amount can be set in the `settings` sheet (`cit_amount`).

- **Not yet assessed**: advances show as *CIT prepayment* on the balance sheet; P&L shows advances as the tax expense.
- **Assessed**: the definitive amount is the P&L tax expense. The difference between advances paid and the definitive amount shows as *CIT receivable* (overpaid) or *CIT payable* (underpaid) on the balance sheet.

## License

AGPL-3.0
