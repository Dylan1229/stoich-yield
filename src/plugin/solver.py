"""pin_yield, the answer key: the exact balancing, limiting reagent(s) and theoretical yield.

The coefficients are the reaction matrix's rational nullspace (Fraction Gaussian elimination), which
must be one-dimensional and strictly positive; every other quantity is an exact Fraction.
"""

from __future__ import annotations

import math
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from contract import PinnedGiven, PinnedSpecies, PinnedYieldOutput, ReactionInput
from plugin.formula import Formula, data_sha256, elements_of, molar_mass, weights_of
from plugin.reaction import reaction

# Two given reactants' extents (moles / coefficient) that differ must differ by more than this share of
# the smaller, so the limiting reagent can be judged by hand: a closer pair is refused as a near tie.
NEAR_TIE = Fraction(1, 100)


def nullspace(matrix: list[list[Fraction]], width: int) -> list[list[Fraction]]:
    """A basis of the vectors v with matrix . v = 0, one per free column of its reduced row echelon form."""
    rows = [list(row) for row in matrix]
    pivots: list[int] = []
    for column in range(width):
        rank = len(pivots)
        pivot = next((index for index in range(rank, len(rows)) if rows[index][column] != 0), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        lead = rows[rank][column]
        rows[rank] = [entry / lead for entry in rows[rank]]
        for index, row in enumerate(rows):
            if index != rank and row[column] != 0:
                factor = row[column]
                rows[index] = [entry - factor * top for entry, top in zip(row, rows[rank], strict=True)]
        pivots.append(column)
    basis = []
    for free in (column for column in range(width) if column not in pivots):
        vector = [Fraction(0)] * width
        vector[free] = Fraction(1)
        for rank, column in enumerate(pivots):
            vector[column] = -rows[rank][free]
        basis.append(vector)
    return basis


def integers(vector: list[Fraction]) -> list[int]:
    """``vector`` scaled to the smallest integers with its signs."""
    scale = math.lcm(*(entry.denominator for entry in vector))
    whole = [int(entry * scale) for entry in vector]
    divisor = math.gcd(*whole)
    return [entry // divisor for entry in whole]


def balance(reactants: list[Formula], products: list[Formula]) -> list[int]:
    """The unique smallest positive integer coefficients conserving every element and the charge, reactants
    first; ValueError when there is no such balancing or more than one independent balancing."""
    species = reactants + products
    signs = [1] * len(reactants) + [-1] * len(products)
    elements = sorted({element for formula in species for element in formula.counts})
    matrix = [
        [Fraction(sign * formula.counts.get(element, 0)) for formula, sign in zip(species, signs, strict=True)]
        for element in elements
    ]
    matrix.append([Fraction(sign * formula.charge) for formula, sign in zip(species, signs, strict=True)])
    basis = nullspace(matrix, len(species))
    if not basis:
        raise ValueError(
            "cannot be balanced with positive coefficients: only all-zero coefficients conserve every element and"
            " the charge"
        )
    if len(basis) > 1:
        raise ValueError(
            f"ambiguous: {len(basis)} independent balancings conserve every element and the charge, so the smallest"
            " positive integer coefficients are not unique"
        )
    vector = integers(basis[0])
    if all(entry < 0 for entry in vector):
        vector = [-entry for entry in vector]
    if not all(entry > 0 for entry in vector):
        if next(entry for entry in vector if entry) < 0:
            vector = [-entry for entry in vector]
        shown = ", ".join(f"{formula.text} {entry}" for formula, entry in zip(species, vector, strict=True))
        raise ValueError(f"cannot be balanced with positive coefficients: the only balancing is {shown}")
    return vector


def decimal_text(value: Fraction) -> str:
    """A terminating fraction as its exact decimal, e.g. 44097/1000 -> 44.097."""
    places = 0
    while (value * 10**places).denominator != 1:
        places += 1
        if places > 40:
            raise ValueError(f"{value} is not a short decimal")
    return format(Decimal(int(value * 10**places)).scaleb(-places), "f")


def fraction_text(value: Fraction) -> str:
    """An exact fraction as p/q, e.g. 44009/5333 (q is 1 for an integer)."""
    return f"{value.numerator}/{value.denominator}"


def pinned_species(formula: Formula) -> PinnedSpecies:
    mass = molar_mass(formula)
    return PinnedSpecies(
        formula=formula.text,
        elements=elements_of(formula),
        charge=formula.charge,
        molar_mass=float(mass),
        molar_mass_exact=decimal_text(mass),
    )


def pin_yield(value: ReactionInput, workspace: Path) -> PinnedYieldOutput:
    checked = reaction(value.reactants, value.products, value.given, value.target)
    coefficients = balance(checked.reactants, checked.products)
    reactant_coefficients = coefficients[: len(checked.reactants)]
    product_coefficients = coefficients[len(checked.reactants) :]
    coefficient_of = dict(zip(value.reactants, reactant_coefficients, strict=True))
    mass_of = {formula.text: molar_mass(formula) for formula in checked.reactants}
    extents = {name: grams / mass_of[name] / coefficient_of[name] for name, grams in checked.given.items()}
    smallest = min(extents.values())
    for name, extent in extents.items():
        if smallest < extent <= smallest * (1 + NEAR_TIE):
            low = next(other for other, size in extents.items() if size == smallest)
            share = float((extent - smallest) / smallest * 100)
            raise ValueError(
                f"near tie: the extents (moles / coefficient) of {low!r} and {name!r} differ by only {share:.3f}%;"
                " give masses whose extents are equal or more than 1% apart, so the limiting reagent can be judged"
                " by hand"
            )
    target = checked.products[checked.target]
    exact_yield = smallest * product_coefficients[checked.target] * molar_mass(target)
    return PinnedYieldOutput(
        reactants=[pinned_species(formula) for formula in checked.reactants],
        products=[pinned_species(formula) for formula in checked.products],
        reactant_coefficients=reactant_coefficients,
        product_coefficients=product_coefficients,
        given=[
            PinnedGiven(
                formula=entry.formula,
                grams=entry.grams,
                grams_exact=decimal_text(checked.given[entry.formula]),
                moles=float(checked.given[entry.formula] / mass_of[entry.formula]),
                extent=float(extents[entry.formula]),
                extent_exact=fraction_text(extents[entry.formula]),
            )
            for entry in value.given
        ],
        limiting=[name for name in value.reactants if extents.get(name) == smallest],
        target=value.target,
        theoretical_yield_g=float(exact_yield),
        theoretical_yield_exact=fraction_text(exact_yield),
        atomic_weights=weights_of(checked.reactants + checked.products),
        data_sha256=data_sha256(),
    )
