"""Generic application context for CLI apps built on TyperPlus."""

from dataclasses import dataclass

import typer


@dataclass(frozen=True, slots=True)
class AppContext[SvcT, OutT, CfgT]:
    """Shared application state passed through Typer context.

    Generic over service, output, and config types.
    Stored in ``ctx.obj`` by the CLI callback, extracted in commands via :func:`use_context`.

    Consumer defines a type alias::

        Context = AppContext[Service, Output, Config]

    """

    svc: SvcT
    out: OutT
    cfg: CfgT


def use_context[T](ctx: typer.Context, _context_type: type[T]) -> T:
    """Extract typed application context from Typer context.

    Args:
        ctx: Typer context (passed automatically to commands).
        _context_type: The expected context type (used only for type inference, not at runtime).

    """
    return ctx.obj  # type: ignore[no-any-return]
