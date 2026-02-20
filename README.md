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

## License

AGPL-3.0
