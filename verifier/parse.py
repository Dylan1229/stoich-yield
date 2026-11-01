"""parse_formula's checks: every formula well formed, and each parse equal to the verifier's own reading."""

import re
from fractions import Fraction

from .checks import result
from .formula import read_formula

MAX_FORMULAS = 12
DECIMAL = re.compile(r"[0-9]+(?:\.[0-9]+)?")


def verify_input(value):
    if not 1 <= len(value.formulas) <= MAX_FORMULAS:
        return result(False, f"formulas must hold 1 to {MAX_FORMULAS} formulas, not {len(value.formulas)}")
    for text in value.formulas:
        _formula, problem = read_formula(text)
        if problem:
            return result(False, f"malformed formula {text!r}: {problem}")
    return result(True, "input is valid")


def weights_problem(atomic_weights, elements):
    """({element: exact weight}, None) or (None, what is wrong): one positive decimal weight per element
    present, sorted by symbol."""
    listed = [entry.element for entry in atomic_weights]
    if listed != sorted(elements):
        return None, f"atomic_weights lists {listed}, not the elements present {sorted(elements)}"
    weights = {}
    for entry in atomic_weights:
        if not DECIMAL.fullmatch(entry.weight) or Fraction(entry.weight) <= 0:
            return None, f"the atomic weight of {entry.element} is {entry.weight!r}, not a positive decimal"
        weights[entry.element] = Fraction(entry.weight)
    return weights, None


def species_problem(row, formula, weights):
    """What is wrong with a parsed row (its atoms, charge and molar mass) against the verifier's reading, or None."""
    atoms = [[entry.element, entry.count] for entry in row.elements]
    if atoms != [[element, count] for element, count in formula["counts"].items()]:
        return f"{row.formula}: atoms {atoms} differ from the verifier's reading {formula['counts']}"
    if row.charge != formula["charge"]:
        return f"{row.formula}: charge {row.charge} differs from the verifier's reading {formula['charge']}"
    exact = sum((weights[element] * count for element, count in formula["counts"].items()), Fraction(0))
    if row.molar_mass != float(exact):
        return f"{row.formula}: molar_mass {row.molar_mass!r} is not the sum of count x weight, {float(exact)!r}"
    return None


def verify_output(input_value, output_value, workspace):
    checked = verify_input(input_value)
    if not checked["valid"]:
        return checked
    if [row.formula for row in output_value.species] != list(input_value.formulas):
        return result(False, "species do not echo the formulas, one each in the order given")
    read = [read_formula(text)[0] for text in input_value.formulas]
    weights, problem = weights_problem(
        output_value.atomic_weights, {element for formula in read for element in formula["counts"]}
    )
    if problem:
        return result(False, problem)
    for row, formula in zip(output_value.species, read, strict=True):
        if row.normalized != formula["normalized"]:
            return result(False, f"{row.formula}: normalized {row.normalized!r}, not {formula['normalized']!r}")
        problem = species_problem(row, formula, weights)
        if problem:
            return result(False, problem)
    return result(True, "every formula is parsed as the verifier reads it", formulas=len(read))
