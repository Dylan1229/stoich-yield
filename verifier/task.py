"""The balance-and-yield verdict: 11 named checks, in order. Valid only when all hold; the score is the share
that hold. Balance is judged with the verifier's own parser (formula.py), the answer against the pinned
answer key after it re-derives exactly (pin.py), and the yield within 0.1% of the exact value."""

import math
from dataclasses import asdict
from fractions import Fraction

from .checks import (
    check,
    coefficients_problem,
    differences,
    imbalance,
    reaction_problem,
    saved_worksheet,
    verdict,
    worksheet_path,
)
from .pin import answer_key

TOLERANCE = Fraction(1, 1000)  # a reported yield passes within 0.1% of the exact yield


def _not_checked(identifier, needs):
    return check(identifier, None, message=f"not checked: {needs} failed")


def _saved_checks(arguments, output, sides, workspace):
    """saved and file-matches: the worksheet save_worksheet wrote for this task, equal to the submission."""
    if sides is None:
        return [_not_checked("saved", "task-input"), _not_checked("file-matches", "task-input")]
    expected = worksheet_path(arguments)
    saved, problem = saved_worksheet(workspace, output.path, expected)
    entries = [check("saved", saved is not None, expected, output.path, problem)]
    if saved is None:
        return entries + [_not_checked("file-matches", "saved")]
    differ = differences(saved, asdict(output))
    message = (
        f"the saved worksheet differs from the submission in {', '.join(differ)}: submit exactly what"
        " save_worksheet returned"
    )
    return entries + [check("file-matches", not differ, [], differ, message)]


def _balance_checks(output, sides):
    """coefficients-form, elements-balanced and charge-balanced, by the verifier's own parser."""
    if sides is None:
        return [
            _not_checked(name, "task-input") for name in ("coefficients-form", "elements-balanced", "charge-balanced")
        ]
    left, right = sides
    reactant, product = output.reactant_coefficients, output.product_coefficients
    shown = {"reactants": list(reactant), "products": list(product)}
    problem = coefficients_problem("reactants", left, reactant) or coefficients_problem("products", right, product)
    if problem:
        return [check("coefficients-form", False, None, shown, problem)] + [
            _not_checked(name, "coefficients-form") for name in ("elements-balanced", "charge-balanced")
        ]
    divisor = math.gcd(*reactant, *product)
    form = check(
        "coefficients-form",
        divisor == 1,
        1,
        divisor,
        f"the coefficients have gcd {divisor}: divide them by it for the smallest integers",
    )
    off, charges = imbalance(left, right, reactant, product)
    elements = check(
        "elements-balanced",
        not off,
        {},
        off,
        "not every element is conserved: "
        + "; ".join(f"{element} {counts[0]} on the left, {counts[1]} on the right" for element, counts in off.items()),
    )
    charge = check(
        "charge-balanced",
        charges[0] == charges[1],
        "equal",
        charges,
        f"the total charge is {charges[0]} on the left but {charges[1]} on the right",
    )
    return [form, elements, charge]


def _answer_checks(output, answer):
    """coefficients, limiting and yield, against the answer key."""
    if answer is None:
        return [_not_checked(name, "reference") for name in ("coefficients", "limiting", "yield")]
    submitted = {"reactants": list(output.reactant_coefficients), "products": list(output.product_coefficients)}
    pinned = {"reactants": answer["reactant_coefficients"], "products": answer["product_coefficients"]}
    coefficients = check(
        "coefficients",
        submitted == pinned,
        pinned,
        submitted,
        f"the coefficients are not the unique smallest positive integers {pinned['reactants']} -> {pinned['products']}",
    )
    limiting = check(
        "limiting",
        list(output.limiting) == answer["limiting"],
        answer["limiting"],
        list(output.limiting),
        f"the limiting reagent(s) are {answer['limiting']} (smallest moles / coefficient, ties in reactant order),"
        f" not {list(output.limiting)}",
    )
    exact = answer["yield"]
    reported = output.theoretical_yield_g
    if not math.isfinite(reported) or reported <= 0:
        return [
            coefficients,
            limiting,
            check(
                "yield",
                False,
                float(exact),
                reported,
                f"theoretical_yield_g {reported!r} is not a positive number of grams",
            ),
        ]
    off = abs(Fraction(reported) - exact)
    share = float(off / exact * 100)
    within = check(
        "yield",
        off <= exact * TOLERANCE,
        float(exact),
        reported,
        f"theoretical_yield_g {reported!r} g is {share:.3f}% from the exact yield {float(exact)!r} g; at most 0.1%"
        " is accepted",
    )
    return [coefficients, limiting, within]


def verify_task(arguments, output, reference, workspace):
    """``output``: a contract WorksheetOutput; ``reference``: pin_yield's PinnedYieldOutput, or None."""
    sides, problem = reaction_problem(arguments)
    answer, key_problem = answer_key(arguments, reference)
    echoed = {"reactants": list(output.reactants), "products": list(output.products)}
    asked = {"reactants": list(arguments.reactants), "products": list(arguments.products)}
    checks = [
        check("task-input", sides is not None, None, None, f"the task input is invalid: {problem}"),
        check("reference", answer is not None, None, None, key_problem),
        check(
            "echo",
            echoed == asked,
            asked,
            echoed,
            "the submission's reactants and products are not the task's, in its order",
        ),
        *_saved_checks(arguments, output, sides, workspace),
        *_balance_checks(output, sides),
        *_answer_checks(output, answer),
    ]
    exact = "" if answer is None else f"{answer['yield'].numerator}/{answer['yield'].denominator}"
    success = (
        f"All {len(checks)} checks hold: limiting {', '.join(output.limiting)}, yield {output.theoretical_yield_g!r} g"
    )
    return {**verdict(checks, success), "details": {"checks": checks, "exact_yield": exact, "tolerance": "0.1%"}}
