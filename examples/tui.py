"""TUI components showcase — interactive demo of all modal screens."""

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import Footer, Label, Log

from mm_clikit import ModalConfirmScreen, ModalInputScreen, ModalListPickerScreen, ModalTextAreaScreen

DEMO_ITEMS = ["Python", "Rust", "Go", "TypeScript", "Java", "C++", "Kotlin", "Swift", "Ruby", "Elixir"]


class TuiShowcase(App[None]):
    """Interactive showcase for mm-clikit TUI components."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("1", "demo_confirm", "Confirm"),
        Binding("2", "demo_input", "Input"),
        Binding("3", "demo_textarea", "TextArea"),
        Binding("4", "demo_picker", "ListPicker"),
        Binding("5", "demo_picker_no_empty", "Picker (no empty)"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Build the main layout."""
        yield Label("[bold]mm-clikit TUI Showcase[/]\n\nPress 1-5 to open modal screens. Results are logged below.\n")
        yield Log(id="log")
        yield Footer()

    def _log(self, msg: str) -> None:
        """Append a line to the log widget."""
        self.query_one("#log", Log).write_line(msg)

    def action_demo_confirm(self) -> None:
        """Demo: ModalConfirmScreen."""
        self.push_screen(ModalConfirmScreen("Delete everything?"), self._on_confirm)

    def _on_confirm(self, result: bool | None) -> None:
        self._log(f"[Confirm] result={result}")

    def action_demo_input(self) -> None:
        """Demo: ModalInputScreen."""
        self.push_screen(ModalInputScreen("Enter your name", "John", placeholder="Type here..."), self._on_input)

    def _on_input(self, result: str | None) -> None:
        self._log(f"[Input] result={result!r}")

    def action_demo_textarea(self) -> None:
        """Demo: ModalTextAreaScreen."""
        self.push_screen(ModalTextAreaScreen("Edit description", "Hello\nWorld"), self._on_textarea)

    def _on_textarea(self, result: str | None) -> None:
        if result is not None:
            preview = result.replace("\n", "\\n")[:80]
            self._log(f"[TextArea] result={preview!r}")
        else:
            self._log("[TextArea] result=None (cancelled)")

    def action_demo_picker(self) -> None:
        """Demo: ModalListPickerScreen with empty option."""
        self.push_screen(
            ModalListPickerScreen(items=DEMO_ITEMS, title="Pick a language", current="Go", empty_label="Any"),
            self._on_picker,
        )

    def _on_picker(self, result: str | None) -> None:
        self._log(f"[Picker] result={result!r}")

    def action_demo_picker_no_empty(self) -> None:
        """Demo: ModalListPickerScreen without empty option."""
        self.push_screen(
            ModalListPickerScreen(items=DEMO_ITEMS, title="Pick a language (required)", current="Rust", empty_label=None),
            self._on_picker_no_empty,
        )

    def _on_picker_no_empty(self, result: str | None) -> None:
        self._log(f"[Picker no-empty] result={result!r}")


if __name__ == "__main__":
    TuiShowcase().run()
