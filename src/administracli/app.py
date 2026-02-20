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

from administracli.closing import (
    ClosingStatus,
    check_closing,
    get_open_incoming_invoices,
    get_open_outgoing_invoices,
)
from administracli.excel_io import load_workbook, save_workbook
from administracli.models import Administracli, Categories
from administracli.reports import balance_sheet, profit_and_loss


def _fmt_date(d) -> str:
    """Format a date as YYYY-MM-DD, handling both date and datetime objects."""
    if d is None:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    return str(d)


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


def _build_category_options(data: Administracli) -> list[tuple[str, str | None, str | None]]:
    """Build the list of options for categorisation.

    Returns a list of (label, category, invoice_id) tuples.
    - For plain categories: (label, category_str, None)
    - For open invoices: (label, category_str, invoice._id)
    """
    options: list[tuple[str, str | None, str | None]] = []

    # Plain categories (excluding invoice categories which are only set via invoice match)
    for cat in Categories:
        if cat in (Categories.INCOMING_INVOICE, Categories.OUTGOING_INVOICE):
            continue
        options.append((str(cat), str(cat), None))

    # Open incoming invoices (costs / creditors)
    open_incoming = get_open_incoming_invoices(data)
    for oi in open_incoming:
        inv = oi.invoice
        label = f"⬇ {inv.counterparty}  {inv.amount}  {_fmt_date(inv.date)}  (open: {oi.balance})"
        options.append((label, str(Categories.INCOMING_INVOICE), inv._id))

    # Open outgoing invoices (revenue / debtors)
    open_outgoing = get_open_outgoing_invoices(data)
    for oi in open_outgoing:
        inv = oi.invoice
        label = f"⬆ {inv.counterparty}  {inv.amount}  {_fmt_date(inv.date)}  (open: {oi.balance})"
        options.append((label, str(Categories.OUTGOING_INVOICE), inv._id))

    return options


class CategoriseScreen(Screen):
    """Assign categories to uncategorised transactions, one at a time."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, data: Administracli, file_path: str, status: ClosingStatus) -> None:
        super().__init__()
        self.data = data
        self.file_path = file_path
        self.uncategorised = list(status.uncategorised)
        self._current = 0
        self._options: list[tuple[str, str | None, str | None]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(id="progress-label")
        yield DataTable(id="txn-display")
        yield OptionList(id="cat-options")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#txn-display", DataTable)
        table.add_columns("Date", "Amount", "Bank Account", "Description")
        table.cursor_type = "none"
        self._show_current()

    def _show_current(self) -> None:
        if self._current >= len(self.uncategorised):
            self.app.pop_screen()
            return
        txn = self.uncategorised[self._current]
        table = self.query_one("#txn-display", DataTable)
        table.clear()
        table.add_row(
            _fmt_date(txn.date), str(txn.amount), txn.bank_account, txn.description or ""
        )
        self.query_one("#progress-label", Label).update(
            f"Transaction {self._current + 1}/{len(self.uncategorised)} — select a category:"
        )

        # Rebuild options each time (open invoices change as we match)
        self._options = _build_category_options(self.data)
        option_list = self.query_one("#cat-options", OptionList)
        option_list.clear_options()
        for label, _, _ in self._options:
            option_list.add_option(label)
        option_list.highlighted = 0
        option_list.focus()

    @on(OptionList.OptionSelected, "#cat-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        idx = event.option_index
        _, category, invoice_id = self._options[idx]

        txn = self.uncategorised[self._current]
        txn._category = category

        if category == str(Categories.INCOMING_INVOICE) and invoice_id:
            txn._incoming_invoice_id = invoice_id
        elif category == str(Categories.OUTGOING_INVOICE) and invoice_id:
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

        lines = [
            Text("Closing status", style="bold underline"),
            Text(""),
            Text(f"  Uncategorised transactions:  {n_uncat}"),
            Text(""),
            Text("Press Enter to proceed.", style="bold"),
        ]

        display = self.query_one("#status-display", Static)
        display.update(Text("\n").join(lines))

    def action_proceed(self) -> None:
        if self.status is None:
            return
        if len(self.status.uncategorised) > 0:
            self.app.push_screen(
                CategoriseScreen(self.data, self.file_path, self.status)
            )

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
