"""
AdministraCLI TUI application.
"""

from textual import on
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, OptionList, Static

from administracli.closing import get_open_incoming_invoices, get_open_outgoing_invoices
from administracli.excel_io import load_workbook, save_workbook
from administracli.models import Administracli, Categories, Transaction
from administracli.reports import balance_sheet, profit_and_loss


def _fmt_date(d) -> str:
    if d is None:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    return str(d)


def _get_uncategorised(data: Administracli) -> list[Transaction]:
    return [t for t in data.transactions if t._category is None]


def _build_options(data: Administracli) -> list[tuple[str, str, str | None]]:
    """Build (label, category, invoice_id) options for the category picker."""
    options: list[tuple[str, str, str | None]] = []

    for cat in Categories:
        if cat in (Categories.INCOMING_INVOICE, Categories.OUTGOING_INVOICE):
            continue
        options.append((str(cat), str(cat), None))

    for oi in get_open_incoming_invoices(data):
        inv = oi.invoice
        label = f"⬇ {inv.counterparty}  {inv.amount}  {_fmt_date(inv.date)}  (open: {oi.balance})"
        options.append((label, str(Categories.INCOMING_INVOICE), inv._id))

    for oi in get_open_outgoing_invoices(data):
        inv = oi.invoice
        label = f"⬆ {inv.counterparty}  {inv.amount}  {_fmt_date(inv.date)}  (open: {oi.balance})"
        options.append((label, str(Categories.OUTGOING_INVOICE), inv._id))

    return options


class ReportScreen(Screen):
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
    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, data: Administracli, file_path: str) -> None:
        super().__init__()
        self.data = data
        self.file_path = file_path
        self.uncategorised = _get_uncategorised(data)
        self._current = 0
        self._options: list[tuple[str, str, str | None]] = []

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
            self.app.switch_screen(ReportScreen(self.data))
            return

        txn = self.uncategorised[self._current]
        total = len(self.data.transactions)
        done = total - len(self.uncategorised) + self._current
        left = len(self.uncategorised) - self._current

        table = self.query_one("#txn-display", DataTable)
        table.clear()
        table.add_row(
            _fmt_date(txn.date), str(txn.amount), txn.bank_account, txn.description or ""
        )
        self.query_one("#progress-label", Label).update(
            f"Transaction {done + 1}/{total}  ({left} left) — select a category:"
        )

        self._options = _build_options(self.data)
        option_list = self.query_one("#cat-options", OptionList)
        option_list.clear_options()
        for label, _, _ in self._options:
            option_list.add_option(label)
        option_list.highlighted = 0
        option_list.focus()

    @on(OptionList.OptionSelected, "#cat-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        _, category, invoice_id = self._options[event.option_index]
        txn = self.uncategorised[self._current]
        txn._category = category

        if category == str(Categories.INCOMING_INVOICE) and invoice_id:
            txn._incoming_invoice_id = invoice_id
        elif category == str(Categories.OUTGOING_INVOICE) and invoice_id:
            txn._outgoing_invoice_id = invoice_id

        save_workbook(self.file_path, self.data)
        self._current += 1
        self._show_current()

    def action_go_back(self) -> None:
        self.app.exit()


class AdministracliApp(App):
    TITLE = "AdministraCLI"

    def __init__(self, file_path: str) -> None:
        super().__init__()
        self.file_path = file_path

    def on_mount(self) -> None:
        data = load_workbook(self.file_path)
        save_workbook(self.file_path, data)  # persist generated _ids

        if _get_uncategorised(data):
            self.push_screen(CategoriseScreen(data, self.file_path))
        else:
            self.push_screen(ReportScreen(data))
