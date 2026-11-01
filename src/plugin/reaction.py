"""A reaction's species and given masses, checked as every tool takes them, and check_balance."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from contract import CheckBalanceInput, CheckBalanceOutput, ElementBalance, GivenMass
from plugin.formula import Formula, parse

MAX_SPECIES = 6  # formulas per side
MIN_GRAMS = 1e-6
MAX_GRAMS = 1e6


@dataclass(frozen=True)
class Reaction:
    reactants: list[Formula]
    products: list[Formula]
    given: dict[str, Fraction]  # reactant, as given -> its exact mass in grams, in the task's order
    target: int  # the target's index in products


def species(reactants: list[str], products: list[str]) -> tuple[list[Formula], list[Formula]]:
    """Both sides parsed: 1 to 6 formulas each, no species twice on a side or on both sides."""
    for side, texts in (("reactants", reactants), ("products", products)):
        if not 1 <= len(texts) <= MAX_SPECIES:
            raise ValueError(f"{side} must list 1 to {MAX_SPECIES} formulas, not {len(texts)}")
    left = [parse(text) for text in reactants]
    right = [parse(text) for text in products]
    for side, formulas in (("reactants", left), ("products", right)):
        seen: dict[tuple, Formula] = {}
        for formula in formulas:
            if formula.identity in seen:
                raise ValueError(
                    f"duplicate species among the {side}: {seen[formula.identity].text!r} and {formula.text!r}"
                    " have the same atoms and charge"
                )
            seen[formula.identity] = formula
    reactant_of = {formula.identity: formula for formula in left}
    for formula in right:
        if formula.identity in reactant_of:
            raise ValueError(
                f"a species on both sides: reactant {reactant_of[formula.identity].text!r} and product"
                f" {formula.text!r} have the same atoms and charge"
            )
    return left, right


def exact_grams(entry: GivenMass) -> Fraction:
    """A given mass as the exact decimal it is written as (the float's shortest repr): 4.032 is 4032/1000."""
    grams = entry.grams
    if not math.isfinite(grams) or grams <= 0:
        raise ValueError(f"the mass of {entry.formula!r} must be a positive number of grams, not {grams!r}")
    if not MIN_GRAMS <= grams <= MAX_GRAMS:
        raise ValueError(f"the mass of {entry.formula!r} must be from 0.000001 to 1000000 g, not {grams!r}")
    return Fraction(repr(grams))


def reaction(reactants: list[str], products: list[str], given: list[GivenMass], target: str) -> Reaction:
    """The task input checked: its species, its given masses (each a distinct reactant) and its target."""
    left, right = species(reactants, products)
    if not given:
        raise ValueError("given must hold the mass of at least one reactant")
    masses: dict[str, Fraction] = {}
    for entry in given:
        if entry.formula not in reactants:
            raise ValueError(f"given formula {entry.formula!r} is not one of the reactants (spell it as there)")
        if entry.formula in masses:
            raise ValueError(f"duplicate given: {entry.formula!r} is given twice")
        masses[entry.formula] = exact_grams(entry)
    if target not in products:
        raise ValueError(f"target {target!r} is not one of the products (spell it as there)")
    return Reaction(left, right, masses, products.index(target))


def coefficients_fit(side: str, formulas: list[Formula], coefficients: list[int]) -> None:
    if len(coefficients) != len(formulas):
        raise ValueError(
            f"{side} need one coefficient per formula: {len(formulas)} formulas, {len(coefficients)} given"
        )
    if any(coefficient < 1 for coefficient in coefficients):
        raise ValueError(f"{side} coefficients must be positive integers, not {coefficients}")


def tally(formulas: list[Formula], coefficients: list[int]) -> tuple[Counter[str], int]:
    """A side's atoms per element and its total charge under ``coefficients``."""
    atoms: Counter[str] = Counter()
    for formula, coefficient in zip(formulas, coefficients, strict=True):
        atoms.update({element: count * coefficient for element, count in formula.counts.items()})
    return atoms, sum(formula.charge * coefficient for formula, coefficient in zip(formulas, coefficients, strict=True))


def check_balance(value: CheckBalanceInput, workspace: Path) -> CheckBalanceOutput:
    left, right = species(value.reactants, value.products)
    coefficients_fit("reactants", left, value.reactant_coefficients)
    coefficients_fit("products", right, value.product_coefficients)
    atoms_left, charge_left = tally(left, value.reactant_coefficients)
    atoms_right, charge_right = tally(right, value.product_coefficients)
    rows = [
        ElementBalance(
            element=element,
            left=atoms_left[element],
            right=atoms_right[element],
            difference=atoms_left[element] - atoms_right[element],
        )
        for element in sorted(set(atoms_left) | set(atoms_right))
    ]
    return CheckBalanceOutput(
        elements=rows,
        charge_left=charge_left,
        charge_right=charge_right,
        balanced=all(row.difference == 0 for row in rows) and charge_left == charge_right,
        gcd=math.gcd(*value.reactant_coefficients, *value.product_coefficients),
    )
