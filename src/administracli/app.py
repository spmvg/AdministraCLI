"""
Entrypoint of the app.
See the documentation in the `help` sections of every parameter for more information, or run ``python -m administracli --help``.
"""

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, OptionList, Static
from textual.widgets.option_list import Option

from administracli.closing import ClosingStatus, check_closing
from administracli.excel_io import load_workbook, save_workbook
from administracli.models import Administracli, Categories
from administracli.reports import balance_sheet, profit_and_loss


class ReportScreen(Screen):
    """Display balance sheet and profit-and-loss statement."""

    BINDINGS = [("q", "quit_app", "Quit")]

    def __init__(self, data: Administracli) -> None:
        super().__init__()
        self.data = data

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static(balance_sheet(self.data), id="balance-sheet")
            yield Static(profit_and_loss(self.data), id="pnl")
        yield Footer()

    def action_quit_app(self) -> None:
        self.app.exit()


class MatchInvoiceScreen(Screen):
    """Match a transaction to an invoice."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, data: Administracli, file_path: str, transaction_index: int) -> None:
        super().__init__()
        self.data = data
        self.file_path = file_path
        self.txn_idx = transaction_index

    def compose(self) -> ComposeResult:
        yield Header()
        txn = self.data.transactions[self.txn_idx]
        yield Label(f"Match transaction: {txn.date}  {txn.amount}  {txn.description or ''}")

        is_incoming = txn._category == Categories.INCOMING_INVOICE
        invoices = self.data.incoming_invoices if is_incoming else self.data.outgoing_invoices
        label = "incoming" if is_incoming else "outgoing"
        yield Label(f"Select an {label} invoice:")

        table = DataTable(id="invoice-table")
        table.cursor_type = "row"
        yield table
        yield Footer()

    def on_mount(self) -> None:
        txn = self.data.transactions[self.txn_idx]
        is_incoming = txn._category == Categories.INCOMING_INVOICE
        invoices = self.data.incoming_invoices if is_incoming else self.data.outgoing_invoices

        table = self.query_one("#invoice-table", DataTable)
        table.add_columns("Date", "Amount", "Counterparty", "_id")
        for inv in invoices:
            table.add_row(str(inv.date), str(inv.amount), inv.counterparty, inv._id or "")

    @on(DataTable.RowSelected, "#invoice-table")
    def on_invoice_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one("#invoice-table", DataTable)
        row_key = event.row_key
        row_data = table.get_row(row_key)
        invoice_id = row_data[3]  # _id column

        txn = self.data.transactions[self.txn_idx]
        if txn._category == Categories.INCOMING_INVOICE:
            txn._incoming_invoice_id = invoice_id
        else:
            txn._outgoing_invoice_id = invoice_id

        save_workbook(self.file_path, self.data)
        self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()


class CategoriseScreen(Screen):
    """Assign categories to uncategorised transactions."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, data: Administracli, file_path: str, status: ClosingStatus) -> None:
        super().__init__()
        self.data = data
        self.file_path = file_path
        self.status = status
        self._selected_txn_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Select a transaction to categorise:")
        with Horizontal():
            with Vertical(id="txn-panel"):
                table = DataTable(id="txn-table")
                table.cursor_type = "row"
                yield table
            with Vertical(id="cat-panel"):
                yield Label("Category:")
                options = OptionList(
                    *[Option(cat.value, id=cat.value) for cat in Categories],
                    id="cat-options",
                )
                yield options
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#txn-table", DataTable)
        table.add_columns("Date", "Amount", "Bank Account", "Description")
        for txn in self.status.uncategorised:
            table.add_row(
                str(txn.date),
                str(txn.amount),
                txn.bank_account,
                txn.description or "",
            )

    @on(DataTable.RowSelected, "#txn-table")
    def on_txn_selected(self, event: DataTable.RowSelected) -> None:
        row_index = event.cursor_row
        self._selected_txn_index = row_index

    @on(OptionList.OptionSelected, "#cat-options")
    def on_category_selected(self, event: OptionList.OptionSelected) -> None:
        if self._selected_txn_index is None:
            return

        txn = self.status.uncategorised[self._selected_txn_index]
        category = event.option.id
        txn._category = category

        save_workbook(self.file_path, self.data)

        # If this is an invoice category, go to matching screen
        if category in (Categories.INCOMING_INVOICE, Categories.OUTGOING_INVOICE):
            global_idx = self.data.transactions.index(txn)
            self.app.push_screen(
                MatchInvoiceScreen(self.data, self.file_path, global_idx)
            )
        else:
            # Refresh: go back to dashboard
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()


class MatchUnmatchedScreen(Screen):
    """Show unmatched invoice-category transactions and let user match them."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, data: Administracli, file_path: str, unmatched: list, label: str) -> None:
        super().__init__()
        self.data = data
        self.file_path = file_path
        self.unmatched = unmatched
        self.label = label

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(f"Unmatched {self.label} transactions — select to match:")
        table = DataTable(id="unmatched-table")
        table.cursor_type = "row"
        yield table
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#unmatched-table", DataTable)
        table.add_columns("Date", "Amount", "Bank Account", "Description")
        for txn in self.unmatched:
            table.add_row(
                str(txn.date), str(txn.amount), txn.bank_account, txn.description or ""
            )

    @on(DataTable.RowSelected, "#unmatched-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        row_index = event.cursor_row
        txn = self.unmatched[row_index]
        global_idx = self.data.transactions.index(txn)
        self.app.push_screen(
            MatchInvoiceScreen(self.data, self.file_path, global_idx)
        )

    def action_go_back(self) -> None:
        self.app.pop_screen()


class DashboardScreen(Screen):
    """Main closing dashboard showing outstanding items."""

    BINDINGS = [
        ("c", "categorise", "Categorise"),
        ("i", "match_incoming", "Match incoming"),
        ("o", "match_outgoing", "Match outgoing"),
        ("r", "refresh", "Refresh"),
        ("q", "quit_app", "Quit"),
    ]

    def __init__(self, data: Administracli, file_path: str) -> None:
        super().__init__()
        self.data = data
        self.file_path = file_path
        self.status: ClosingStatus | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static(id="status-display")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_status()

    def on_screen_resume(self) -> None:
        # Reload data from disk to pick up any changes
        self.data = load_workbook(self.file_path)
        self._refresh_status()

    def _refresh_status(self) -> None:
        self.status = check_closing(self.data)

        if self.status.is_closed:
            self.app.push_screen(ReportScreen(self.data))
            return

        lines = [
            Text("Closing status", style="bold underline"),
            Text(""),
        ]

        n_uncat = len(self.status.uncategorised)
        n_in = len(self.status.unmatched_incoming)
        n_out = len(self.status.unmatched_outgoing)
        n_uref_in = len(self.status.unreferenced_incoming)
        n_uref_out = len(self.status.unreferenced_outgoing)

        lines.append(Text(f"  Uncategorised transactions:       {n_uncat}"))
        lines.append(Text(f"  Unmatched incoming invoices:       {n_in}"))
        lines.append(Text(f"  Unmatched outgoing invoices:       {n_out}"))
        lines.append(Text(f"  Unreferenced incoming invoices:    {n_uref_in}"))
        lines.append(Text(f"  Unreferenced outgoing invoices:    {n_uref_out}"))
        lines.append(Text(""))

        hints = []
        if n_uncat > 0:
            hints.append("[c] Categorise transactions")
        if n_in > 0:
            hints.append("[i] Match incoming invoices")
        if n_out > 0:
            hints.append("[o] Match outgoing invoices")
        if n_uref_in > 0 or n_uref_out > 0:
            hints.append("Add transactions in Excel for unreferenced invoices, then [r] Refresh")
        hints.append("[q] Quit")

        lines.append(Text("Actions:", style="bold"))
        for h in hints:
            lines.append(Text(f"  {h}"))

        display = self.query_one("#status-display", Static)
        combined = Text("\n").join(lines)
        display.update(combined)

    def action_categorise(self) -> None:
        if self.status and len(self.status.uncategorised) > 0:
            self.app.push_screen(
                CategoriseScreen(self.data, self.file_path, self.status)
            )

    def action_match_incoming(self) -> None:
        if self.status and len(self.status.unmatched_incoming) > 0:
            self.app.push_screen(
                MatchUnmatchedScreen(
                    self.data, self.file_path, self.status.unmatched_incoming, "incoming invoice"
                )
            )

    def action_match_outgoing(self) -> None:
        if self.status and len(self.status.unmatched_outgoing) > 0:
            self.app.push_screen(
                MatchUnmatchedScreen(
                    self.data, self.file_path, self.status.unmatched_outgoing, "outgoing invoice"
                )
            )

    def action_refresh(self) -> None:
        self.data = load_workbook(self.file_path)
        self._refresh_status()

    def action_quit_app(self) -> None:
        self.app.exit()


class AdministracliApp(App):
    """Main Textual application."""

    TITLE = "AdministraCLI"
    CSS = """
    #txn-panel {
        width: 60%;
    }
    #cat-panel {
        width: 40%;
    }
    """

    def __init__(self, file_path: str) -> None:
        super().__init__()
        self.file_path = file_path

    def on_mount(self) -> None:
        data = load_workbook(self.file_path)
        # Ensure _ids are generated and persisted
        save_workbook(self.file_path, data)
        self.push_screen(DashboardScreen(data, self.file_path))
