"""
Entrypoint of the app.
See the documentation in the `help` sections of every parameter for more information, or run ``python -m administracli --help``.
"""

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, OptionList, Static

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


class CategoriseScreen(Screen):
    """Assign categories to uncategorised transactions, one at a time."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, data: Administracli, file_path: str, status: ClosingStatus) -> None:
        super().__init__()
        self.data = data
        self.file_path = file_path
        self.uncategorised = list(status.uncategorised)
        self._current = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(id="txn-label")
        yield Label(id="progress-label")
        yield OptionList(
            *[str(cat) for cat in Categories],
            id="cat-options",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._show_current()

    def _show_current(self) -> None:
        if self._current >= len(self.uncategorised):
            self.app.pop_screen()
            return
        txn = self.uncategorised[self._current]
        self.query_one("#txn-label", Label).update(
            f"  {txn.date}    {txn.amount}    {txn.bank_account}    {txn.description or ''}"
        )
        self.query_one("#progress-label", Label).update(
            f"Transaction {self._current + 1}/{len(self.uncategorised)} — select a category:"
        )
        option_list = self.query_one("#cat-options", OptionList)
        option_list.highlighted = 0
        option_list.focus()

    @on(OptionList.OptionSelected, "#cat-options")
    def on_category_selected(self, event: OptionList.OptionSelected) -> None:
        categories = list(Categories)
        category = categories[event.option_index]
        txn = self.uncategorised[self._current]
        txn._category = str(category)
        save_workbook(self.file_path, self.data)

        if category in (Categories.INCOMING_INVOICE, Categories.OUTGOING_INVOICE):
            self._current += 1
            self.app.push_screen(
                MatchUnmatchedScreen(self.data, self.file_path, [txn])
            )
        else:
            self._current += 1
            self._show_current()

    def on_screen_resume(self) -> None:
        self._show_current()

    def action_go_back(self) -> None:
        self.app.pop_screen()


class MatchUnmatchedScreen(Screen):
    """Walk through unmatched invoice-category transactions one at a time."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, data: Administracli, file_path: str, unmatched: list) -> None:
        super().__init__()
        self.data = data
        self.file_path = file_path
        self.unmatched = list(unmatched)
        self._current = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(id="match-txn-label")
        yield Label(id="match-progress-label")
        table = DataTable(id="unmatched-table")
        table.cursor_type = "row"
        yield table
        yield Footer()

    def on_mount(self) -> None:
        self._show_current()

    def _show_current(self) -> None:
        if self._current >= len(self.unmatched):
            self.app.pop_screen()
            return
        txn = self.unmatched[self._current]
        self.query_one("#match-txn-label", Label).update(
            f"  {txn.date}    {txn.amount}    {txn.bank_account}    {txn.description or ''}"
        )
        is_incoming = txn._category == Categories.INCOMING_INVOICE
        invoices = self.data.incoming_invoices if is_incoming else self.data.outgoing_invoices
        label = "incoming" if is_incoming else "outgoing"
        self.query_one("#match-progress-label", Label).update(
            f"Unmatched {self._current + 1}/{len(self.unmatched)} — select an {label} invoice:"
        )
        table = self.query_one("#unmatched-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Date", "Amount", "Counterparty", "_id")
        for inv in invoices:
            table.add_row(str(inv.date), str(inv.amount), inv.counterparty, inv._id or "")
        table.focus()

    @on(DataTable.RowSelected, "#unmatched-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one("#unmatched-table", DataTable)
        row_data = table.get_row(event.row_key)
        invoice_id = row_data[3]

        txn = self.unmatched[self._current]
        if txn._category == Categories.INCOMING_INVOICE:
            txn._incoming_invoice_id = invoice_id
        else:
            txn._outgoing_invoice_id = invoice_id

        save_workbook(self.file_path, self.data)
        self._current += 1
        self._show_current()

    def on_screen_resume(self) -> None:
        self._show_current()

    def action_go_back(self) -> None:
        self.app.pop_screen()


class DashboardScreen(Screen):
    """Main screen: show closing status, proceed to reconcile or view reports."""

    BINDINGS = [
        ("enter", "proceed", "Proceed"),
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
        self.data = load_workbook(self.file_path)
        self._refresh_status()

    def _refresh_status(self) -> None:
        self.status = check_closing(self.data)

        if self.status.is_closed:
            self.app.push_screen(ReportScreen(self.data))
            return

        n_uncat = len(self.status.uncategorised)
        n_in = len(self.status.unmatched_incoming)
        n_out = len(self.status.unmatched_outgoing)
        n_uref_in = len(self.status.unreferenced_incoming)
        n_uref_out = len(self.status.unreferenced_outgoing)

        lines = [
            Text("Closing status", style="bold underline"),
            Text(""),
            Text(f"  Uncategorised transactions:       {n_uncat}"),
            Text(f"  Unmatched incoming invoices:       {n_in}"),
            Text(f"  Unmatched outgoing invoices:       {n_out}"),
            Text(f"  Unreferenced incoming invoices:    {n_uref_in}"),
            Text(f"  Unreferenced outgoing invoices:    {n_uref_out}"),
            Text(""),
        ]

        if n_uref_in > 0 or n_uref_out > 0:
            lines.append(Text(
                "⚠ Unreferenced invoices: add matching transactions in Excel, then refresh.",
                style="bold yellow",
            ))
            lines.append(Text(""))

        if n_uncat > 0 or n_in > 0 or n_out > 0:
            lines.append(Text("Press Enter to proceed.", style="bold"))
        else:
            lines.append(Text("Press [r] to refresh after editing Excel.", style="bold"))

        display = self.query_one("#status-display", Static)
        display.update(Text("\n").join(lines))

    def action_proceed(self) -> None:
        if self.status is None:
            return
        if len(self.status.uncategorised) > 0:
            self.app.push_screen(
                CategoriseScreen(self.data, self.file_path, self.status)
            )
        elif len(self.status.unmatched_incoming) + len(self.status.unmatched_outgoing) > 0:
            unmatched = self.status.unmatched_incoming + self.status.unmatched_outgoing
            self.app.push_screen(
                MatchUnmatchedScreen(self.data, self.file_path, unmatched)
            )

    def action_refresh(self) -> None:
        self.data = load_workbook(self.file_path)
        self._refresh_status()

    def action_quit_app(self) -> None:
        self.app.exit()


class AdministracliApp(App):
    """Main Textual application."""

    TITLE = "AdministraCLI"

    def __init__(self, file_path: str) -> None:
        super().__init__()
        self.file_path = file_path

    def on_mount(self) -> None:
        data = load_workbook(self.file_path)
        # Ensure _ids are generated and persisted
        save_workbook(self.file_path, data)
        self.push_screen(DashboardScreen(data, self.file_path))
