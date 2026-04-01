"""Generic core context for CLI apps built on TyperPlus."""

import typer
from pydantic import BaseModel, ConfigDict


class CoreContext[CoreT, OutT](BaseModel):
    """Shared application state passed through Typer context.

    Generic over core (composition root) and output types.
    Stored in ``ctx.obj`` by the CLI callback, extracted in commands via :func:`use_context`.

    Consumer defines a type alias::

        Context = CoreContext[Core, Output]

    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    core: CoreT
    out: OutT


def use_context[T](ctx: typer.Context, _context_type: type[T]) -> T:
    """Extract typed application context from Typer context.

    Args:
        ctx: Typer context (passed automatically to commands).
        _context_type: The expected context type (used only for type inference, not at runtime).

    """
    return ctx.obj  # type: ignore[no-any-return]
