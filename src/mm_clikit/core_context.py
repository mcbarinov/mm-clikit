"""Generic core context for CLI apps built on TyperPlus."""

import typer
from pydantic import BaseModel, ConfigDict


class CoreContext[CoreT, OutT = None](BaseModel):
    """Shared application state passed through Typer context.

    Generic over core (composition root) and an output type.
    Stored in ``ctx.obj`` by the CLI callback, extracted in commands via :func:`use_context`.

    Apps without a dedicated Output class (no ``--json`` support) use
    ``CoreContext[Core](core=core, out=None)``. Apps with a ``DualModeOutput`` subclass
    use ``CoreContext[Core, Output](core=core, out=Output())`` — ``app.out`` is then
    typed as ``Output`` directly, with no ``| None`` widening.
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
