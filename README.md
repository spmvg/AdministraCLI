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

TODO: since AdministraCLI doesn't have assets and the transactions are usually just for that year (not the total administration), the balance sheet shows differences, not totals.

TODO: separate AdministraCLI for every year

## Corporate income tax

CIT advance payments are categorised as `Corporate income tax` like any other transaction.
The definitive CIT amount can be set in the `settings` sheet (`cit_amount`).

- **Not yet assessed**: advances show as *CIT prepayment* on the balance sheet. Nothing appears in the P&L.
- **Assessed**: the definitive amount appears as tax expense in the P&L. The difference between advances paid and the definitive amount shows as *CIT receivable* (overpaid) or *CIT payable* (underpaid) on the balance sheet.

## License

AGPL-3.0
