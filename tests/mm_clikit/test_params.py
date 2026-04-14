"""Tests for custom click ParamType implementations."""

from decimal import Decimal
from typing import Any, cast

import click
import pytest

from mm_clikit import DecimalParam


class TestValidValues:
    """Tests for parsing valid decimal strings."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("0", Decimal(0)),
            ("1", Decimal(1)),
            ("-1.5", Decimal("-1.5")),
            ("0.0001", Decimal("0.0001")),
            ("1e2", Decimal(100)),
            ("-3.14159", Decimal("-3.14159")),
        ],
    )
    def test_parses_string(self, raw: str, expected: Decimal) -> None:
        """Plain string values are parsed into Decimal."""
        assert DecimalParam().convert(raw, None, None) == expected

    def test_passthrough_decimal(self) -> None:
        """An already-converted Decimal passes through unchanged (click calls convert on defaults)."""
        value = Decimal("42.5")
        assert DecimalParam().convert(value, None, None) is value


class TestInvalidValues:
    """Tests for rejection of invalid input."""

    @pytest.mark.parametrize("raw", ["abc", "", "1.2.3", "--", "1,5"])
    def test_rejects_garbage(self, raw: str) -> None:
        """Non-decimal strings raise UsageError."""
        with pytest.raises(click.UsageError, match="not a valid decimal"):
            DecimalParam().convert(raw, None, None)

    @pytest.mark.parametrize("raw", ["Inf", "-Inf", "Infinity", "NaN", "-NaN"])
    def test_rejects_non_finite(self, raw: str) -> None:
        """Inf and NaN are always rejected."""
        with pytest.raises(click.UsageError, match="not a finite decimal"):
            DecimalParam().convert(raw, None, None)


class TestBounds:
    """Tests for inclusive and exclusive range bounds."""

    def test_inclusive_lower_accepts_equal(self) -> None:
        """Inclusive lower bound accepts the boundary value."""
        assert DecimalParam(lower="10").convert("10", None, None) == Decimal(10)

    def test_inclusive_lower_rejects_below(self) -> None:
        """Inclusive lower bound rejects values strictly below."""
        with pytest.raises(click.UsageError, match=">= 10"):
            DecimalParam(lower="10").convert("9.99", None, None)

    def test_exclusive_lower_rejects_equal(self) -> None:
        """Exclusive lower bound rejects the boundary value."""
        with pytest.raises(click.UsageError, match="> 10"):
            DecimalParam(lower="10", lower_open=True).convert("10", None, None)

    def test_exclusive_lower_accepts_above(self) -> None:
        """Exclusive lower bound accepts values strictly above."""
        assert DecimalParam(lower="10", lower_open=True).convert("10.01", None, None) == Decimal("10.01")

    def test_inclusive_upper_accepts_equal(self) -> None:
        """Inclusive upper bound accepts the boundary value."""
        assert DecimalParam(upper="100").convert("100", None, None) == Decimal(100)

    def test_inclusive_upper_rejects_above(self) -> None:
        """Inclusive upper bound rejects values strictly above."""
        with pytest.raises(click.UsageError, match="<= 100"):
            DecimalParam(upper="100").convert("100.01", None, None)

    def test_exclusive_upper_rejects_equal(self) -> None:
        """Exclusive upper bound rejects the boundary value."""
        with pytest.raises(click.UsageError, match="< 100"):
            DecimalParam(upper="100", upper_open=True).convert("100", None, None)

    def test_both_bounds(self) -> None:
        """A value inside a closed range is accepted."""
        param = DecimalParam(lower="0", upper="1")
        assert param.convert("0.5", None, None) == Decimal("0.5")


class TestBoundConstruction:
    """Tests for normalization of bound types passed to __init__."""

    @pytest.mark.parametrize("bound", [Decimal("1.5"), 2, "3.14"])
    def test_accepts_decimal_int_str(self, bound: Decimal | int | str) -> None:
        """Bounds may be Decimal, int, or str — all normalized internally."""
        param = DecimalParam(lower=bound)
        assert isinstance(param.lower, Decimal)

    def test_rejects_float(self) -> None:
        """Float bounds are rejected to prevent precision surprises."""
        with pytest.raises(TypeError, match="bound must be"):
            DecimalParam(lower=cast(Any, 1.5))
