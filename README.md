# AdministraCLI

TODO: Command line tool for small business administration with local data in an Excel sheet

### Principles
* Data is stored locally in an Excel sheet
* AdministraCLI will interactively guide the users to make sure the books are closed (transaction matching to invoices, groups added, etc.).
* If the data is complete, AdministraCLI will show a balance sheet and profit-and-loss statement.
* The Excel sheet has the following format:
  * Worksheets are tables with column names and data in rows. For example: transactions is a worksheet, which contains columns Date and Amount.
  * Columns starting with an underscore `_...` are intended for system use by AdministraCLI. Users shouldn't touch those columns in Excel.
  * AdministraCLI can initiatialize an empty Excel sheet with the proper format. The user can then enter their data in Excel.