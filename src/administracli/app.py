"""
AdministraCLI TUI application.
"""

from decimal import Decimal

from textual import on
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, OptionList, Static

from administracli.closing import get_open_incoming_invoices, get_open_outgoing_invoices, get_open_vat_declarations
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


def _cross_booking_balance(data: Administracli) -> Decimal:
    """Sum of all cross_booking transactions. Must be zero for valid books."""
    return sum(
        (t.amount for t in data.transactions if t._category == str(Categories.CROSS_BOOKING)),
        Decimal(0),
    )


def _build_options(data: Administracli) -> list[tuple[str, str, str | None, str | None]]:
    """Build (label, category, invoice_id, vat_declaration_id) options for the category picker."""
    options: list[tuple[str, str, str | None, str | None]] = []

    for cat in Categories:
        if cat in (Categories.INCOMING_INVOICE, Categories.OUTGOING_INVOICE):
            continue
        options.append((str(cat), str(cat), None, None))

    for oi in get_open_incoming_invoices(data):
        inv = oi.invoice
        label = f"⬇ {inv.counterparty}  {inv.amount}  {_fmt_date(inv.date)}  (open: {oi.balance})"
        options.append((label, str(Categories.INCOMING_INVOICE), inv._id, None))

    for oi in get_open_outgoing_invoices(data):
        inv = oi.invoice
        label = f"⬆ {inv.counterparty}  {inv.amount}  {_fmt_date(inv.date)}  (open: {oi.balance})"
        options.append((label, str(Categories.OUTGOING_INVOICE), inv._id, None))

    for ov in get_open_vat_declarations(data):
        decl = ov.declaration
        label = (
            f"🧾 VAT {_fmt_date(decl.period_start_date_inclusive)}–{_fmt_date(decl.period_end_date_exclusive)}"
            f"  owed: {ov.owed:,.2f}  paid: {ov.paid:,.2f}  (open: {ov.balance:,.2f})"
        )
        options.append((label, str(Categories.VAT), None, decl._id))

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


class CrossBookingErrorScreen(Screen):
    """Shown when cross-bookings don't sum to zero."""

    BINDINGS = [("q", "quit_app", "Quit")]

    def __init__(self, imbalance: Decimal) -> None:
        super().__init__()
        self.imbalance = imbalance

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            f"\n  ❌ Cross-bookings do not sum to zero (imbalance: {self.imbalance:,.2f}).\n\n"
            f"  Cross-bookings are transfers between your own bank accounts.\n"
            f"  They must cancel out. Fix the categorisation in Excel and re-run.\n",
        )
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
        self._options: list[tuple[str, str, str | None, str | None]] = []
        self._filtered_indices: list[int] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(id="progress-label")
        yield Static(id="txn-display")
        yield Input(placeholder="Type to filter…", id="filter-input")
        yield OptionList(id="cat-options")
        yield Footer()

    def on_mount(self) -> None:
        self._show_current()

    def _show_current(self) -> None:
        if self._current >= len(self.uncategorised):
            imbalance = _cross_booking_balance(self.data)
            if imbalance != Decimal(0):
                self.app.switch_screen(CrossBookingErrorScreen(imbalance))
            else:
                self.app.switch_screen(ReportScreen(self.data))
            return

        txn = self.uncategorised[self._current]
        total = len(self.data.transactions)
        done = total - len(self.uncategorised) + self._current
        left = len(self.uncategorised) - self._current

        self.query_one("#txn-display", Static).update(
            f"[bold]Date:[/bold] {_fmt_date(txn.date)}   "
            f"[bold]Amount:[/bold] {txn.amount}   "
            f"[bold]Account:[/bold] {txn.bank_account}\n"
            f"[bold]Description:[/bold] {txn.description or ''}"
        )
        self.query_one("#progress-label", Label).update(
            f"Transaction {done + 1}/{total}  ({left} left) — select a category:"
        )

        self._options = _build_options(self.data)
        filter_input = self.query_one("#filter-input", Input)
        filter_input.value = ""
        self._apply_filter("")
        filter_input.focus()

    def _apply_filter(self, query: str) -> None:
        q = query.lower()
        self._filtered_indices = [
            i for i, (label, _, _, _) in enumerate(self._options) if q in label.lower()
        ]
        option_list = self.query_one("#cat-options", OptionList)
        option_list.clear_options()
        for i in self._filtered_indices:
            option_list.add_option(self._options[i][0])
        if self._filtered_indices:
            option_list.highlighted = 0

    @on(Input.Changed, "#filter-input")
    def on_filter_changed(self, event: Input.Changed) -> None:
        self._apply_filter(event.value)

    @on(Input.Submitted, "#filter-input")
    def on_filter_submitted(self, event: Input.Submitted) -> None:
        """Enter in the filter input selects the highlighted option."""
        if not self._filtered_indices:
            return
        option_list = self.query_one("#cat-options", OptionList)
        highlighted = option_list.highlighted
        if highlighted is not None:
            self._select_option(highlighted)

    @on(OptionList.OptionSelected, "#cat-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if not self._filtered_indices:
            return
        self._select_option(event.option_index)

    def _select_option(self, filtered_index: int) -> None:
        original_index = self._filtered_indices[filtered_index]
        _, category, invoice_id, vat_declaration_id = self._options[original_index]
        txn = self.uncategorised[self._current]
        txn._category = category

        if category == str(Categories.INCOMING_INVOICE) and invoice_id:
            txn._incoming_invoice_id = invoice_id
        elif category == str(Categories.OUTGOING_INVOICE) and invoice_id:
            txn._outgoing_invoice_id = invoice_id
        elif category == str(Categories.VAT) and vat_declaration_id:
            txn._vat_declaration_id = vat_declaration_id

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
            imbalance = _cross_booking_balance(data)
            if imbalance != Decimal(0):
                self.push_screen(CrossBookingErrorScreen(imbalance))
            else:
                self.push_screen(ReportScreen(data))
