"""save_worksheet's checks: a well-shaped answer to a valid task, saved where the verifier looks for it."""

import math
from dataclasses import asdict

from .checks import coefficients_problem, differences, reaction_problem, result, saved_worksheet, worksheet_path


def verify_input(value):
    sides, problem = reaction_problem(value)
    if problem:
        return result(False, problem)
    problem = coefficients_problem("reactants", sides[0], value.reactant_coefficients) or coefficients_problem(
        "products", sides[1], value.product_coefficients
    )
    if problem:
        return result(False, problem)
    given = [entry.formula for entry in value.given]
    if not value.limiting:
        return result(False, "limiting must name at least one given reactant")
    for name in value.limiting:
        if name not in given:
            return result(False, f"limiting {name!r} is not a given reactant (spell it as in reactants)")
    if len(set(value.limiting)) != len(value.limiting):
        return result(False, "limiting names a reactant twice")
    if not math.isfinite(value.theoretical_yield_g) or value.theoretical_yield_g <= 0:
        return result(
            False, f"theoretical_yield_g must be a positive number of grams, not {value.theoretical_yield_g!r}"
        )
    return result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    checked = verify_input(input_value)
    if not checked["valid"]:
        return checked
    fields = (
        "reactants",
        "products",
        "reactant_coefficients",
        "product_coefficients",
        "limiting",
        "theoretical_yield_g",
    )
    given, made = asdict(input_value), asdict(output_value)
    changed = [field for field in fields if given[field] != made[field]]
    if changed:
        return result(False, f"the saved answer changes {', '.join(changed)}")
    saved, problem = saved_worksheet(workspace, output_value.path, worksheet_path(input_value))
    if problem:
        return result(False, problem)
    differ = differences(saved, made)
    if differ:
        return result(False, f"the file {output_value.path} differs from the output in {', '.join(differ)}")
    return result(True, "the worksheet is saved", path=output_value.path)
