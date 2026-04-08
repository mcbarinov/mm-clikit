"""Modal full-screen text area editor."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.screen import ModalScreen
from textual.widgets import Footer, Label, TextArea


class ModalTextAreaScreen(ModalScreen[str | None]):
    """Full-screen multi-line text editor. Returns text on Ctrl+S, None on Escape."""

    DEFAULT_CSS = """
    ModalTextAreaScreen {
        background: $surface;
    }
    ModalTextAreaScreen .modal-textarea-header {
        padding: 0 1;
    }
    ModalTextAreaScreen .modal-textarea-area {
        height: 1fr;
        margin: 0 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(self, title: str, value: str = "") -> None:
        """Initialize with title and current text content."""
        super().__init__()
        self._title = title  # Header text
        self._value = value  # Pre-fill content

    def compose(self) -> ComposeResult:
        """Build the editor layout."""
        yield Label(f"[bold]{self._title}[/]", classes="modal-textarea-header")
        yield TextArea(self._value, classes="modal-textarea-area", soft_wrap=False)
        yield Footer()

    def on_mount(self) -> None:
        """Focus the text area on open."""
        self.query_one(TextArea).focus()

    def action_save(self) -> None:
        """Save via Ctrl+S."""
        self.dismiss(self.query_one(TextArea).text)

    def action_cancel(self) -> None:
        """Cancel via escape key."""
        self.dismiss(None)
