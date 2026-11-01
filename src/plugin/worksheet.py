"""save_worksheet: the agent's answer, checked for shape only, saved as worksheets/<slug>.json."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from slimconfig import plain_output

from contract import GivenMass, WorksheetInput, WorksheetOutput
from plugin.reaction import coefficients_fit, reaction

FOLDER = "worksheets"
READABLE = 60  # characters of the slug's readable part


def _piece(formula: str) -> str:
    """A formula in a file name: + as p, - as m, every other run of non-alphanumerics as _."""
    return re.sub(r"[^A-Za-z0-9]+", "_", formula.replace("+", "p").replace("-", "m")).strip("_") or "x"


def worksheet_path(reactants: list[str], products: list[str], given: list[GivenMass], target: str) -> str:
    """worksheets/<target>-from-<reactants>-<digest>.json: the digest (sha256 of the task input as compact,
    key-sorted JSON) tells apart tasks whose readable part is the same."""
    readable = f"{_piece(target)}-from-{'-'.join(_piece(name) for name in reactants)}"[:READABLE].rstrip("-_")
    task = {
        "reactants": reactants,
        "products": products,
        "given": [[entry.formula, entry.grams] for entry in given],
        "target": target,
    }
    digest = hashlib.sha256(json.dumps(task, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:10]
    return f"{FOLDER}/{readable}-{digest}.json"


def save_worksheet(value: WorksheetInput, workspace: Path) -> WorksheetOutput:
    checked = reaction(value.reactants, value.products, value.given, value.target)
    coefficients_fit("reactants", checked.reactants, value.reactant_coefficients)
    coefficients_fit("products", checked.products, value.product_coefficients)
    if not value.limiting:
        raise ValueError("limiting must name at least one given reactant")
    for name in value.limiting:
        if name not in checked.given:
            raise ValueError(f"limiting {name!r} is not a given reactant (spell it as in reactants)")
    if len(set(value.limiting)) != len(value.limiting):
        raise ValueError("limiting names a reactant twice")
    if not math.isfinite(value.theoretical_yield_g) or value.theoretical_yield_g <= 0:
        raise ValueError(f"theoretical_yield_g must be a positive number of grams, not {value.theoretical_yield_g!r}")
    relative = worksheet_path(value.reactants, value.products, value.given, value.target)
    root = workspace.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"{relative} would leave the plugin workspace")
    output = WorksheetOutput(
        reactants=list(value.reactants),
        products=list(value.products),
        reactant_coefficients=list(value.reactant_coefficients),
        product_coefficients=list(value.product_coefficients),
        limiting=list(value.limiting),
        theoretical_yield_g=value.theoretical_yield_g,
        path=relative,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    # Saving again replaces the worksheet: the last save is the answer.
    path.write_text(json.dumps(plain_output(output), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output
