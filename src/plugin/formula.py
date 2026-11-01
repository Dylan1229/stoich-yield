"""Chemical formulas: the grammar, the atomic weight table, and parse_formula.

The grammar (case-sensitive, no spaces)::

    formula   := part (("*" | "·") [multiplier] part)* [charge]
    part      := unit+
    unit      := (symbol | "(" part ")" | "[" part "]") [count]
    symbol    := an uppercase letter and an optional lowercase letter, an element of the table
    count, multiplier := a positive integer without leading zeros
    charge    := "^" [positive integer] ("+" | "-")

So ``Co`` is cobalt and ``CO`` carbon and oxygen, ``CuSO4*5H2O`` is a hydrate, ``K4[Fe(CN)6]`` nests
groups and ``MnO4^-`` is an ion. The first part takes no multiplier: ``2H2O`` is a coefficient, not a formula.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from pathlib import Path

from contract import AtomicWeight, ElementCount, ParsedFormula, ParseFormulaInput, ParseFormulaOutput

DATA = Path(__file__).with_name("data") / "atomic_weights.json"
MAX_LENGTH = 100  # characters in one formula
MAX_FORMULAS = 12  # formulas in one parse_formula call
SEPARATORS = "*·"
DIGITS = "0123456789"


@dataclass(frozen=True)
class Formula:
    text: str  # as given
    normalized: str
    counts: dict[str, int]  # element symbol -> atoms, every count positive
    charge: int

    @property
    def identity(self) -> tuple[tuple[tuple[str, int], ...], int]:
        """What makes two formulas the same species: their atoms and charge."""
        return tuple(sorted(self.counts.items())), self.charge


@cache
def table() -> dict[str, str]:
    """Element symbol -> its standard atomic weight, the table's decimal text."""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    return {row["symbol"]: row["weight"] for row in data["elements"]}


@cache
def data_sha256() -> str:
    return hashlib.sha256(DATA.read_bytes()).hexdigest()


class _Parser:
    """A recursive-descent parser over one formula's text."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.at = 0

    def fail(self, reason: str) -> ValueError:
        return ValueError(f"malformed formula {self.text!r}: {reason}")

    def peek(self) -> str | None:
        return self.text[self.at] if self.at < len(self.text) else None

    def number(self) -> int | None:
        """A positive integer at the cursor, or None when there is no digit."""
        start = self.at
        while self.peek() is not None and self.peek() in DIGITS:
            self.at += 1
        if start == self.at:
            return None
        digits = self.text[start : self.at]
        if digits[0] == "0":
            raise self.fail(f"{digits!r} at position {start + 1} is not a positive integer without leading zeros")
        return int(digits)

    def part(self, closer: str | None) -> tuple[Counter[str], str]:
        """Units up to ``closer`` (a bracket), a separator, the charge or the end."""
        counts: Counter[str] = Counter()
        shown: list[str] = []
        while True:
            char = self.peek()
            if char is None or char in SEPARATORS or char in "^)]":
                break
            start = self.at
            if char in "([":
                self.at += 1
                want = ")" if char == "(" else "]"
                inner, text = self.part(want)
                if self.peek() != want:
                    found = "the end" if self.peek() is None else repr(self.peek())
                    raise self.fail(f"{char!r} at position {start + 1} is closed by {found}, not {want!r}")
                if not inner:
                    raise self.fail(f"empty brackets at position {start + 1}")
                self.at += 1
                count = self.number() or 1
                unit = Counter({element: atoms * count for element, atoms in inner.items()})
                shown.append(f"{char}{text}{want}{count if count != 1 else ''}")
            elif "A" <= char <= "Z":
                self.at += 1
                if self.peek() is not None and "a" <= self.peek() <= "z":
                    self.at += 1
                symbol = self.text[start : self.at]
                if symbol not in table():
                    raise self.fail(f"unknown element {symbol!r} (not in the atomic weight table)")
                count = self.number() or 1
                unit = Counter({symbol: count})
                shown.append(f"{symbol}{count if count != 1 else ''}")
            else:
                raise self.fail(f"unexpected {char!r} at position {start + 1}")
            counts.update(unit)
        if closer is None and self.peek() is not None and self.peek() in ")]":
            raise self.fail(f"{self.peek()!r} at position {self.at + 1} closes no bracket")
        return counts, "".join(shown)

    def formula(self) -> Formula:
        if not self.text:
            raise self.fail("it is empty")
        if len(self.text) > MAX_LENGTH:
            raise self.fail(f"it is longer than {MAX_LENGTH} characters")
        if self.text[0] in DIGITS:
            raise self.fail("it starts with a number: a coefficient such as 2H2O is not a formula (write H2O)")
        counts, first = self.part(None)
        if not counts:
            raise self.fail(f"unexpected {self.text[0]!r} at position 1: a formula starts with an element or bracket")
        parts = [first]
        while self.peek() is not None and self.peek() in SEPARATORS:
            self.at += 1
            multiplier = self.number() or 1
            more, text = self.part(None)
            if not more:
                raise self.fail(f"the hydrate part at position {self.at + 1} holds no element")
            counts.update({element: atoms * multiplier for element, atoms in more.items()})
            parts.append(f"{multiplier if multiplier != 1 else ''}{text}")
        charge, suffix = 0, ""
        if self.peek() == "^":
            self.at += 1
            size = self.number() or 1
            sign = self.peek()
            if sign is None or sign not in "+-":
                raise self.fail("a charge is ^ then an optional positive integer then + or -, e.g. ^2+")
            self.at += 1
            charge = size if sign == "+" else -size
            suffix = f"^{size if size != 1 else ''}{sign}"
        if self.peek() is not None:
            raise self.fail(f"unexpected {self.peek()!r} at position {self.at + 1}")
        return Formula(self.text, "*".join(parts) + suffix, dict(sorted(counts.items())), charge)


def parse(text: str) -> Formula:
    """``text`` parsed under the grammar, or ValueError saying why it is malformed."""
    return _Parser(text).formula()


def molar_mass(formula: Formula) -> Fraction:
    """g/mol, exactly: the sum of count x atomic weight, each weight the table's decimal."""
    weights = table()
    return sum((Fraction(weights[element]) * count for element, count in formula.counts.items()), Fraction(0))


def elements_of(formula: Formula) -> list[ElementCount]:
    return [ElementCount(element=element, count=count) for element, count in sorted(formula.counts.items())]


def weights_of(formulas: list[Formula]) -> list[AtomicWeight]:
    """The table's weight of every element in ``formulas``, sorted by symbol."""
    present = sorted({element for formula in formulas for element in formula.counts})
    return [AtomicWeight(element=element, weight=table()[element]) for element in present]


def parse_formula(value: ParseFormulaInput, workspace: Path) -> ParseFormulaOutput:
    if not 1 <= len(value.formulas) <= MAX_FORMULAS:
        raise ValueError(f"formulas must hold 1 to {MAX_FORMULAS} formulas, not {len(value.formulas)}")
    parsed = [parse(text) for text in value.formulas]
    return ParseFormulaOutput(
        species=[
            ParsedFormula(
                formula=formula.text,
                normalized=formula.normalized,
                elements=elements_of(formula),
                charge=formula.charge,
                molar_mass=float(molar_mass(formula)),
            )
            for formula in parsed
        ],
        atomic_weights=weights_of(parsed),
    )
