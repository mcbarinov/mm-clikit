"""Modal confirmation dialog screen."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label


class ModalConfirmScreen(ModalScreen[bool]):
    """Simple yes/no confirmation dialog. Returns True on confirm, False on cancel."""

    DEFAULT_CSS = """
    ModalConfirmScreen {
        align: center middle;
    }
    ModalConfirmScreen .modal-dialog {
        width: 1fr;
        height: auto;
        margin: 0 4;
        padding: 0 1;
        background: $surface;
    }
    ModalConfirmScreen .modal-confirm-hint {
        color: $text-muted;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, message: str) -> None:
        """Initialize with the confirmation message."""
        super().__init__()
        self.message = message  # Text to display in the dialog

    def compose(self) -> ComposeResult:
        """Build the confirmation dialog."""
        with Vertical(classes="modal-dialog"):
            yield Label(self.message)
            yield Label("[dim]y[/]:yes  [dim]n[/]:no", classes="modal-confirm-hint")

    def action_confirm(self) -> None:
        """Confirm via y key."""
        self.dismiss(True)

    def action_cancel(self) -> None:
        """Cancel via n/escape key."""
        self.dismiss(False)
