"""Custom click ParamType implementations for mm-clikit CLIs."""

from decimal import Decimal, InvalidOperation

import click


def _to_decimal(value: Decimal | int | str) -> Decimal:
    """Normalize a bound value to Decimal. Rejects float to avoid precision surprises."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | str):
        return Decimal(value)
    raise TypeError(f"bound must be Decimal, int, or str; got {type(value).__name__}")


class DecimalParam(click.ParamType):
    """Parse a CLI value into ``decimal.Decimal`` with optional inclusive/exclusive range bounds.

    Mirrors ``click.FloatRange``: bounds are inclusive by default; pass
    ``lower_open`` / ``upper_open`` for strict comparisons. Non-finite values
    (``Inf``, ``-Inf``, ``NaN``) are always rejected.
    """

    name = "decimal"  # Drives click's default metavar

    def __init__(
        self,
        *,
        lower: Decimal | int | str | None = None,
        upper: Decimal | int | str | None = None,
        lower_open: bool = False,
        upper_open: bool = False,
    ) -> None:
        """Configure the allowed range. Bounds are inclusive unless the matching ``*_open`` flag is set."""
        self.lower = _to_decimal(lower) if lower is not None else None  # Lower bound (None = unbounded)
        self.upper = _to_decimal(upper) if upper is not None else None  # Upper bound (None = unbounded)
        self.lower_open = lower_open  # True = strict >, False = >=
        self.upper_open = upper_open  # True = strict <, False = <=

    def convert(self, value: object, param: click.Parameter | None, ctx: click.Context | None) -> Decimal:
        """Convert and validate a raw CLI string into a ``Decimal``."""
        if isinstance(value, Decimal):
            result = value
        else:
            try:
                result = Decimal(str(value))
            except InvalidOperation:
                self.fail(f"{value!r} is not a valid decimal", param, ctx)
        if not result.is_finite():
            self.fail(f"{value!r} is not a finite decimal (Inf/NaN not allowed)", param, ctx)
        if self.lower is not None:
            if self.lower_open and result <= self.lower:
                self.fail(f"{value} must be > {self.lower}", param, ctx)
            if not self.lower_open and result < self.lower:
                self.fail(f"{value} must be >= {self.lower}", param, ctx)
        if self.upper is not None:
            if self.upper_open and result >= self.upper:
                self.fail(f"{value} must be < {self.upper}", param, ctx)
            if not self.upper_open and result > self.upper:
                self.fail(f"{value} must be <= {self.upper}", param, ctx)
        return result
