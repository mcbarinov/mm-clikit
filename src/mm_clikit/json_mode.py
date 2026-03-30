"""Helper for accessing the --json flag set by TyperPlus."""

import click


def get_json_mode() -> bool:
    """Read the ``--json`` flag from Click context.

    Returns ``True`` when the current TyperPlus app was invoked with ``--json``.
    Safe to call even without an active Click context (returns ``False``).
    """
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return False
    result: bool = ctx.find_root().meta.get("_json_mode", False)
    return result
