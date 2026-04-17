"""Tests for TUI modal screens via Textual's Pilot."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from textual.app import App
from textual.screen import ModalScreen

from mm_clikit.tui import ModalConfirmScreen, ModalInputScreen, ModalListPickerScreen, ModalTextAreaScreen

_UNSET: Any = object()


class _Host(App[None]):
    """Generic host app that pushes a modal on mount and stores its dismissed value."""

    def __init__(self, screen: ModalScreen[Any]) -> None:
        """Store the screen to be pushed once the app mounts."""
        super().__init__()
        self._screen = screen
        self.result: Any = _UNSET

    def on_mount(self) -> None:
        """Push the modal and capture its return value in ``self.result``."""

        def callback(value: Any) -> None:
            self.result = value

        self.push_screen(self._screen, callback)


def _drive(screen: ModalScreen[Any], steps: Callable[[Any, _Host], Awaitable[None]]) -> Any:
    """Run ``steps`` against a host app hosting ``screen`` and return the dismissed value."""
    host = _Host(screen)

    async def _run() -> None:
        async with host.run_test() as pilot:
            await pilot.pause()
            await steps(pilot, host)
            await pilot.pause()

    asyncio.run(_run())
    return host.result


class TestModalConfirmScreen:
    """Tests for yes/no confirmation dialog."""

    def test_yes_key_returns_true(self) -> None:
        """Pressing y dismisses with True."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("y")

        assert _drive(ModalConfirmScreen("continue?"), steps) is True

    def test_no_key_returns_false(self) -> None:
        """Pressing n dismisses with False."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("n")

        assert _drive(ModalConfirmScreen("continue?"), steps) is False

    def test_escape_returns_false(self) -> None:
        """Pressing Escape dismisses with False."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("escape")

        assert _drive(ModalConfirmScreen("continue?"), steps) is False


class TestModalInputScreen:
    """Tests for single-line input dialog."""

    def test_enter_submits_stripped_value(self) -> None:
        """Enter dismisses with the typed value stripped."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("h", "i", "enter")

        assert _drive(ModalInputScreen("name"), steps) == "hi"

    def test_enter_strips_whitespace(self) -> None:
        """Leading and trailing whitespace is removed before dismissing."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("space", "x", "space", "enter")

        assert _drive(ModalInputScreen("name"), steps) == "x"

    def test_empty_rejected_by_default(self) -> None:
        """Enter on an empty input is a no-op unless allow_empty=True."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("enter")

        assert _drive(ModalInputScreen("name"), steps) is _UNSET

    def test_empty_allowed_returns_empty_string(self) -> None:
        """With allow_empty=True, Enter on empty input dismisses with ""."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("enter")

        assert _drive(ModalInputScreen("name", allow_empty=True), steps) == ""

    def test_escape_returns_none(self) -> None:
        """Escape dismisses with None."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("escape")

        assert _drive(ModalInputScreen("name"), steps) is None

    def test_prefilled_value(self) -> None:
        """A prefilled value survives until Enter is pressed."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("enter")

        assert _drive(ModalInputScreen("name", value="preset"), steps) == "preset"


class TestModalTextAreaScreen:
    """Tests for full-screen text editor."""

    def test_ctrl_s_saves_prefilled_content(self) -> None:
        """Ctrl+S dismisses with the current text area content."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("ctrl+s")

        assert _drive(ModalTextAreaScreen("notes", value="hello"), steps) == "hello"

    def test_escape_returns_none(self) -> None:
        """Escape dismisses with None, discarding any content."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("escape")

        assert _drive(ModalTextAreaScreen("notes", value="unused"), steps) is None

    def test_typed_content_is_saved(self) -> None:
        """Typed characters are returned on Ctrl+S."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("a", "b", "c", "ctrl+s")

        assert _drive(ModalTextAreaScreen("notes"), steps) == "abc"


class TestModalListPickerScreen:
    """Tests for list picker with filtering."""

    def test_escape_returns_none(self) -> None:
        """Escape cancels the picker and returns None."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("escape")

        result = _drive(ModalListPickerScreen(items=["apple", "banana", "cherry"], title="fruit"), steps)
        assert result is None

    def test_empty_label_selection_returns_empty_string(self) -> None:
        """With no ``current`` set, the empty option is pre-highlighted and Enter returns ""."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("enter")

        result = _drive(ModalListPickerScreen(items=["a", "b"], title="pick", current=None), steps)
        assert result == ""

    def test_selects_current_on_enter(self) -> None:
        """With ``current`` set, Enter on empty input selects the current item."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("enter")

        result = _drive(
            ModalListPickerScreen(items=["apple", "banana", "cherry"], title="pick", current="banana"),
            steps,
        )
        assert result == "banana"

    def test_filter_then_enter_selects_first_match(self) -> None:
        """Typing a query narrows the list; Enter selects the first match."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("c", "h", "enter")

        result = _drive(
            ModalListPickerScreen(items=["apple", "banana", "cherry"], title="pick", current="apple"),
            steps,
        )
        assert result == "cherry"

    def test_no_empty_label_still_works(self) -> None:
        """Pickers without an empty label still select the current/highlighted item."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("enter")

        result = _drive(
            ModalListPickerScreen(items=["x", "y"], title="pick", current="y", empty_label=None),
            steps,
        )
        assert result == "y"

    def test_item_labels_do_not_change_return_value(self) -> None:
        """``item_labels`` affects display only; the selected item string is still returned."""

        async def steps(pilot: Any, _host: _Host) -> None:
            await pilot.press("enter")

        result = _drive(
            ModalListPickerScreen(
                items=["id-1", "id-2"],
                title="pick",
                current="id-1",
                item_labels={"id-1": "First", "id-2": "Second"},
            ),
            steps,
        )
        assert result == "id-1"
