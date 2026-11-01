"""check_balance's checks: the tally recomputed with the verifier's own parser."""

import math

from .checks import coefficients_problem, result, side_problem, tally


def verify_input(value):
    sides, problem = side_problem(value.reactants, value.products)
    if problem:
        return result(False, problem)
    problem = coefficients_problem("reactants", sides[0], value.reactant_coefficients) or coefficients_problem(
        "products", sides[1], value.product_coefficients
    )
    if problem:
        return result(False, problem)
    return result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    checked = verify_input(input_value)
    if not checked["valid"]:
        return checked
    left, right = side_problem(input_value.reactants, input_value.products)[0]
    atoms_left, charge_left = tally(left, input_value.reactant_coefficients)
    atoms_right, charge_right = tally(right, input_value.product_coefficients)
    expected = [
        [
            element,
            atoms_left.get(element, 0),
            atoms_right.get(element, 0),
            atoms_left.get(element, 0) - atoms_right.get(element, 0),
        ]
        for element in sorted(set(atoms_left) | set(atoms_right))
    ]
    actual = [[row.element, row.left, row.right, row.difference] for row in output_value.elements]
    if actual != expected:
        return result(False, "the element tally differs from the verifier's", expected=expected, actual=actual)
    if [output_value.charge_left, output_value.charge_right] != [charge_left, charge_right]:
        return result(False, f"the charges are {charge_left} and {charge_right}, not as reported")
    balanced = all(row[3] == 0 for row in expected) and charge_left == charge_right
    if output_value.balanced is not balanced:
        return result(False, f"balanced must be {balanced}")
    divisor = math.gcd(*input_value.reactant_coefficients, *input_value.product_coefficients)
    if output_value.gcd != divisor:
        return result(False, f"gcd must be {divisor}, not {output_value.gcd}")
    return result(True, "the tally is the verifier's", balanced=balanced)
