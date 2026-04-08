"""Modal list picker screen with text filtering."""

from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option


class ModalListPickerScreen(ModalScreen[str | None]):
    """List picker with live text filtering. Returns item string, "" for empty option, None on cancel."""

    DEFAULT_CSS = """
    ModalListPickerScreen {
        align: center middle;
    }
    ModalListPickerScreen .modal-dialog {
        width: 1fr;
        height: auto;
        max-height: 70%;
        margin: 0 4;
        padding: 0 1;
        background: $surface;
    }
    ModalListPickerScreen .modal-picker-input {
        border: solid $accent;
    }
    ModalListPickerScreen .modal-picker-list {
        height: auto;
        max-height: 20;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        *,
        items: list[str],
        title: str,
        current: str | None = None,
        empty_label: str | None = "All",
        item_labels: dict[str, str] | None = None,
    ) -> None:
        """Initialize with available items, current selection, and display options."""
        super().__init__()
        self._items = items  # All available items
        self._current = current  # Currently selected item (None = empty option)
        self._title = title  # Dialog title
        self._empty_label = empty_label  # Label for the "no selection" option
        self._item_labels = item_labels or {}  # Optional display labels (item -> label)
        self._filtered: list[str] = list(items)  # Currently visible items after filtering

    def compose(self) -> ComposeResult:
        """Build the picker with search input and option list."""
        with Vertical(classes="modal-dialog"):
            yield Label(f"[bold]{self._title}[/]")
            yield Input(placeholder="Type to filter...", classes="modal-picker-input")
            yield OptionList(classes="modal-picker-list")

    def on_mount(self) -> None:
        """Populate list and focus the input."""
        self._rebuild_options()
        self.query_one(Input).focus()

    def _rebuild_options(self, query: str = "") -> None:
        """Rebuild the option list based on the search query."""
        option_list = self.query_one(OptionList)
        option_list.clear_options()

        # Optional empty/"all" option at the top
        offset = 0
        if self._empty_label is not None:
            option_list.add_option(Option(self._empty_label, id="opt-empty"))
            offset = 1

        # Filter items by case-insensitive substring match
        query_lower = query.lower()
        self._filtered = [item for item in self._items if query_lower in item.lower()] if query else list(self._items)

        for i, item in enumerate(self._filtered):
            label = self._item_labels.get(item, item)
            option_list.add_option(Option(label, id=f"opt-{i}"))

        # Pre-highlight: first match when filtering, current selection otherwise
        if query and self._filtered:
            option_list.highlighted = offset  # First matching item
        elif not query and self._current:
            for i, item in enumerate(self._filtered):
                if item == self._current:
                    option_list.highlighted = i + offset
                    return
            option_list.highlighted = 0
        else:
            option_list.highlighted = 0

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the list as the user types."""
        self._rebuild_options(event.value)

    @on(Input.Submitted)
    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Select the first matching item on Enter, or the highlighted option if no query."""
        query = self.query_one(Input).value.strip()
        if query:
            if self._filtered:
                self.dismiss(self._filtered[0])
        else:
            option_list = self.query_one(OptionList)
            if option_list.highlighted is not None:
                self._select_by_index(option_list.highlighted)

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option click/Enter selection."""
        self._select_by_index(event.option_index)

    def _select_by_index(self, index: int) -> None:
        """Dismiss with the item at the given index."""
        offset = 1 if self._empty_label is not None else 0
        if offset and index == 0:
            self.dismiss("")  # Empty option
        else:
            self.dismiss(self._filtered[index - offset])

    def action_cancel(self) -> None:
        """Cancel picker."""
        self.dismiss(None)
