"""pin_yield's checks, and the answer key re-derived: every number the key states is recomputed here with
the verifier's own parser and exact fractions, from the key's atomic weights and the task's masses, so a
bug in the answer key fails the verdict instead of passing a wrong answer."""

import math
import re
from fractions import Fraction

from .checks import coefficients_problem, grams_exact, imbalance, reaction_problem, result
from .parse import species_problem, weights_problem

DECIMAL = re.compile(r"[0-9]+(?:\.[0-9]+)?")
FRACTION = re.compile(r"[0-9]+/[1-9][0-9]*")
SHA256 = re.compile(r"[0-9a-f]{64}")


def _decimal(text):
    return Fraction(text) if DECIMAL.fullmatch(text) else None


def _fraction(text):
    return Fraction(text) if FRACTION.fullmatch(text) else None


def _coefficients_problem(key, left, right):
    problem = coefficients_problem("reactants", left, key.reactant_coefficients) or coefficients_problem(
        "products", right, key.product_coefficients
    )
    if problem:
        return problem
    if math.gcd(*key.reactant_coefficients, *key.product_coefficients) != 1:
        return "its coefficients are not the smallest integers (gcd is not 1)"
    off, charges = imbalance(left, right, key.reactant_coefficients, key.product_coefficients)
    if off or charges[0] != charges[1]:
        return f"its coefficients do not balance: elements {off}, charges {charges}"
    return None


def _answer(arguments, key):
    """(the key's answer re-derived, None) or (None, why the key is wrong)."""
    sides, problem = reaction_problem(arguments)
    if problem:
        return None, f"the task input is invalid: {problem}"
    left, right = sides
    if [row.formula for row in key.reactants] != list(arguments.reactants):
        return None, "its reactants are not the task's"
    if [row.formula for row in key.products] != list(arguments.products) or key.target != arguments.target:
        return None, "its products or target are not the task's"
    elements = {element for formula in left + right for element in formula["counts"]}
    weights, problem = weights_problem(key.atomic_weights, elements)
    if problem:
        return None, problem
    masses = {}
    for row, formula in zip(key.reactants + key.products, left + right, strict=True):
        problem = species_problem(row, formula, weights)
        if problem:
            return None, problem
        masses[row.formula] = sum(
            (weights[element] * count for element, count in formula["counts"].items()), Fraction(0)
        )
        if _decimal(row.molar_mass_exact) != masses[row.formula]:
            return None, f"{row.formula}: molar_mass_exact {row.molar_mass_exact!r} is not {masses[row.formula]}"
    problem = _coefficients_problem(key, left, right)
    if problem:
        return None, problem
    if [row.formula for row in key.given] != [entry.formula for entry in arguments.given]:
        return None, "its given reactants are not the task's"
    coefficient_of = dict(zip(arguments.reactants, key.reactant_coefficients, strict=True))
    extents = {}
    for row, entry in zip(key.given, arguments.given, strict=True):
        grams = grams_exact(entry.grams)
        moles = grams / masses[entry.formula]
        extents[entry.formula] = moles / coefficient_of[entry.formula]
        stated = [row.grams, _decimal(row.grams_exact), row.moles, _fraction(row.extent_exact), row.extent]
        if stated != [entry.grams, grams, float(moles), extents[entry.formula], float(extents[entry.formula])]:
            return None, f"{entry.formula}: its grams, moles or extent are not {entry.grams!r} g / M / coefficient"
    smallest = min(extents.values())
    limiting = [name for name in arguments.reactants if extents.get(name) == smallest]
    if list(key.limiting) != limiting:
        return None, f"its limiting reagents {list(key.limiting)} are not the smallest extents' {limiting}"
    target = arguments.products.index(arguments.target)
    exact = smallest * key.product_coefficients[target] * masses[arguments.target]
    if _fraction(key.theoretical_yield_exact) != exact or key.theoretical_yield_g != float(exact):
        return None, f"its theoretical yield {key.theoretical_yield_exact} is not {exact.numerator}/{exact.denominator}"
    if not SHA256.fullmatch(key.data_sha256):
        return None, "its data_sha256 is not a sha256"
    return {
        "reactant_coefficients": list(key.reactant_coefficients),
        "product_coefficients": list(key.product_coefficients),
        "limiting": limiting,
        "yield": exact,
    }, None


def answer_key(arguments, key):
    """(the pinned answer, None) or (None, why there is no answer key to judge by)."""
    if key is None:
        return None, "no answer key: pin_yield was not pinned for this task"
    try:
        answer, problem = _answer(arguments, key)
    except (ArithmeticError, LookupError, ValueError):
        return None, "the answer key is malformed: a number in it cannot be read"
    if problem:
        return None, f"the answer key is inconsistent: {problem}"
    return answer, None


def verify_input(value):
    _sides, problem = reaction_problem(value)
    if problem:
        return result(False, problem)
    return result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    answer, problem = answer_key(input_value, output_value)
    if problem:
        return result(False, problem)
    return result(True, "the answer key re-derives exactly", limiting=answer["limiting"])
