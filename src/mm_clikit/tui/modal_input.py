"""Modal single-line input screen."""

from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label


class ModalInputScreen(ModalScreen[str | None]):
    """Single-line text input dialog. Returns stripped string on Enter, None on Escape."""

    DEFAULT_CSS = """
    ModalInputScreen {
        align: center middle;
    }
    ModalInputScreen .modal-dialog {
        width: 1fr;
        height: auto;
        margin: 0 4;
        padding: 0 1;
        background: $surface;
    }
    ModalInputScreen .modal-input-field {
        border: solid $accent;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, value: str = "", *, placeholder: str = "", allow_empty: bool = False) -> None:
        """Initialize with field metadata and current value."""
        super().__init__()
        self._title = title  # Header text
        self._value = value  # Pre-fill value
        self._placeholder = placeholder  # Input placeholder
        self._allow_empty = allow_empty  # Whether empty submission is valid

    def compose(self) -> ComposeResult:
        """Build the input dialog."""
        with Vertical(classes="modal-dialog"):
            yield Label(f"[bold]{self._title}[/]")
            yield Input(value=self._value, placeholder=self._placeholder, classes="modal-input-field")

    def on_mount(self) -> None:
        """Focus the input and place cursor at end."""
        inp = self.query_one(Input)
        inp.focus()
        inp.cursor_position = len(inp.value)

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Submit on Enter."""
        value = event.value.strip()
        if value or self._allow_empty:
            self.dismiss(value)

    def action_cancel(self) -> None:
        """Cancel via escape key."""
        self.dismiss(None)
