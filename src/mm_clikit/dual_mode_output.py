"""Base class for dual-mode (JSON / display) CLI output."""

from rich.console import Console, RenderableType

from .json_mode import get_json_mode
from .output import print_json


class DualModeOutput:
    """Base for CLI output handlers supporting JSON and display modes.

    JSON mode outputs a unified envelope shared with the default error handler::

        {"ok": true,  "data": {...}, "error": null}
        {"ok": false, "data": null,  "error": {"code": "...", "message": "..."}}

    Clients always see all three keys: ``data`` is the success payload (or ``null``
    on error) and ``error`` is an object with ``code`` / ``message`` (or ``null``
    on success). Display mode outputs human-readable content: plain strings, Rich
    tables, panels, syntax-highlighted blocks, or any ``RenderableType``.

    Reads ``--json`` flag automatically via ``get_json_mode()`` — no constructor
    arguments needed.

    Subclass and add domain-specific methods that prepare ``json_data`` +
    ``display_data`` and delegate to ``output``.
    """

    def __init__(self) -> None:
        """Initialize output handler. Reads --json flag from Click context."""
        self.json_mode = get_json_mode()

    def output(self, *, json_data: dict[str, object], display_data: RenderableType) -> None:
        """Output a result in JSON or display format."""
        if self.json_mode:
            print_json({"ok": True, "data": json_data, "error": None})
        else:
            Console().print(display_data)
